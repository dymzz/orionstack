"""Model-independent regression for Qwen3 prompting, pooling, signatures and bounds."""

from dataclasses import replace
import json
from pathlib import Path
from threading import Lock
from types import SimpleNamespace

import numpy as np
import onnx
import pytest
from tokenizers import Tokenizer, models, pre_tokenizers

from app.config.core_settings import CoreSettings, CoreConfigurationError
from app.knowledge.contracts import content_hash
from app.knowledge.embedding import create_embedding_client, WorkersAIEmbeddingClient
from app.knowledge.onnx_embedding import OnnxEmbeddingClient, QUERY_PREFIX, last_token_pool


@pytest.fixture
def model(tmp_path, monkeypatch):
    root = tmp_path / 'model'; (root / 'onnx').mkdir(parents=True); (root / '1_Pooling').mkdir()
    tensor = onnx.TensorProto(name='weights',data_type=onnx.TensorProto.FLOAT,dims=[1],data_location=onnx.TensorProto.EXTERNAL)
    tensor.external_data.add(key='location',value='model.onnx_data')
    graph = onnx.helper.make_graph([], 'test', [], [], [tensor])
    onnx.save(onnx.helper.make_model(graph), root / 'onnx/model.onnx')
    (root / 'onnx/model.onnx_data').write_bytes(b'weights')
    configs = {
        'config.json': {'hidden_size':1024}, 'tokenizer_config.json':{}, 'modules.json':[],
        '1_Pooling/config.json': {'pooling_mode':'lasttoken','embedding_dimension':1024},
        'sentence_bert_config.json': {'max_seq_length':32768},
        'config_sentence_transformers.json': {'prompts':{'document':'','query':QUERY_PREFIX}},
    }
    for name, value in configs.items(): (root / name).write_text(json.dumps(value),encoding='utf-8')
    tokenizer = Tokenizer(models.WordLevel({'[UNK]':0,'short':1,'long':2,'document':3},unk_token='[UNK]'))
    tokenizer.pre_tokenizer = pre_tokenizers.Whitespace()
    tokenizer.save(str(root / 'tokenizer.json'))
    seen = []
    def run(outputs, feed):
        seen.append(feed)
        values = np.repeat(feed['input_ids'][:,:,None].astype(np.float32),1024,axis=2)
        values[:,:,0] = 1
        return [values]
    runtime = SimpleNamespace(tokenizer=tokenizer,pad_id=999,lock=Lock(),session=SimpleNamespace(run=run))
    monkeypatch.setattr('app.knowledge.onnx_embedding._runtime',lambda *args: runtime)
    client = OnnxEmbeddingClient(CoreSettings(onnx_dir=str(root),onnx_max_tokens=128))
    return client, root, seen


def test_last_token_pool_with_left_right_and_noncontiguous_padding():
    hidden = np.arange(3*4*2).reshape(3,4,2)
    mask = np.array([[0,0,1,1],[1,1,0,0],[1,0,1,0]])
    assert np.array_equal(last_token_pool(hidden,mask),hidden[[0,1,2],[3,1,2]])
    with pytest.raises(ValueError): last_token_pool(hidden,np.zeros((3,4)))


def test_left_padding_positions_exact_hash_and_document_vs_query_prompt(model):
    client, _, seen = model
    batch = client.embed(('short','long document'))
    assert seen[0]['input_ids'].tolist() == [[999,1],[2,3]]
    assert seen[0]['attention_mask'].tolist() == [[0,1],[1,1]]
    assert seen[0]['position_ids'].tolist() == [[0,0],[0,1]]
    assert batch.input_hashes == (content_hash('short'),content_hash('long document'))
    query = client.embed_query('short')
    assert len(seen[1]['input_ids'][0]) > 1
    assert query.input_hashes == (content_hash('short'),) and query.signature == batch.signature
    assert np.allclose(np.linalg.norm(batch.vectors,axis=1),1)


def test_artifact_revision_is_portable_and_changes_with_weights(model,tmp_path):
    client, root, _ = model
    signature = client.signature
    import shutil
    copied = tmp_path/'copy'; shutil.copytree(root,copied)
    assert OnnxEmbeddingClient(replace(client.settings,onnx_dir=str(copied))).signature == signature
    (root/'onnx/model.onnx_data').write_bytes(b'changed weights')
    with pytest.raises(CoreConfigurationError,match='changed'): client.embed(('short',))
    assert OnnxEmbeddingClient(client.settings).signature.fingerprint != signature.fingerprint
    assert OnnxEmbeddingClient(replace(client.settings,onnx_max_tokens=64)).signature.fingerprint != signature.fingerprint


def test_overlong_input_is_rejected_before_inference(model):
    client, _, seen = model
    limited = OnnxEmbeddingClient(replace(client.settings,onnx_max_tokens=1))
    with pytest.raises(ValueError,match='silent truncation'): limited.embed_query('short')
    assert not seen


def test_artifact_cannot_escape_model_directory(model):
    client, root, _ = model
    graph = onnx.load(str(root/'onnx/model.onnx'),load_external_data=False)
    graph.graph.initializer[0].external_data[0].value = '../../elsewhere.data'
    onnx.save(graph,root/'onnx/model.onnx')
    with pytest.raises(CoreConfigurationError,match='escapes'): _ = client.signature


def test_invalid_dimensions_or_query_prompt_rejected(model):
    client, root, _ = model
    with pytest.raises(CoreConfigurationError,match='dimensions'):
        _ = OnnxEmbeddingClient(replace(client.settings,embedding_dimensions=2)).signature
    (root/'config_sentence_transformers.json').write_text('{"prompts":{"query":"wrong","document":""}}',encoding='utf-8')
    with pytest.raises(CoreConfigurationError,match='prompt'): _ = OnnxEmbeddingClient(client.settings).signature


def test_provider_selection_is_explicit_and_does_not_load_model():
    assert isinstance(create_embedding_client(CoreSettings(embedding_provider='onnx',onnx_dir='missing')),OnnxEmbeddingClient)
    assert isinstance(create_embedding_client(CoreSettings(embedding_provider='cloudflare_workers_ai')),WorkersAIEmbeddingClient)
    with pytest.raises(CoreConfigurationError): CoreSettings(embedding_provider='unknown')
