"""Local Qwen3 embeddings using only ONNX Runtime and the bundled Rust tokenizer."""

from functools import lru_cache
import hashlib
import json
from pathlib import Path
from threading import Lock

import numpy as np
import onnx
import onnxruntime as ort
from tokenizers import Tokenizer

from app.config.core_settings import CoreConfigurationError, CoreSettings
from app.knowledge.contracts import content_hash
from app.knowledge.embedding import EmbeddingBatch, EmbeddingSignature, normalized_vector
from app.providers.http import ProviderError


QUERY_PREFIX = "Instruct: Given a web search query, retrieve relevant passages that answer the query\nQuery:"
_RUNTIME_LOCK = Lock()


def last_token_pool(hidden: np.ndarray, mask: np.ndarray) -> np.ndarray:
    if (hidden.ndim != 3 or mask.shape != hidden.shape[:2]
            or not np.all(np.isin(mask, (0, 1))) or np.any(mask.sum(axis=1) == 0)):
        raise ValueError("Invalid hidden states or attention mask")
    # Absolute final nonpadding position works with left and right padding.
    positions = np.where(mask == 1, np.arange(mask.shape[1]), -1).max(axis=1)
    return hidden[np.arange(hidden.shape[0]), positions]


@lru_cache(maxsize=16)
def _artifact_digest(stamps: tuple) -> str:
    digest = hashlib.sha256()
    for relative, path, size, modified in stamps:
        digest.update(relative.encode("utf-8") + b"\0")
        with Path(path).open("rb") as stream:
            while block := stream.read(8 * 1024 * 1024):
                digest.update(block)
        info = Path(path).stat()
        if info.st_size != size or info.st_mtime_ns != modified:
            raise CoreConfigurationError("ONNX artifacts changed during fingerprinting")
        digest.update(b"\0")
    return digest.hexdigest()


class _Runtime:
    def __init__(self, model_path: Path, tokenizer_path: Path, threads: int):
        options = ort.SessionOptions()
        options.intra_op_num_threads = threads
        options.inter_op_num_threads = 1
        options.log_severity_level = 3
        self.session = ort.InferenceSession(str(model_path), sess_options=options,
                                           providers=["CPUExecutionProvider"])
        self.session.disable_fallback()
        if ({i.name for i in self.session.get_inputs()} != {"input_ids", "attention_mask", "position_ids"}
                or "last_hidden_state" not in {o.name for o in self.session.get_outputs()}):
            raise CoreConfigurationError("Local ONNX graph does not match the Qwen3 embedding contract")
        self.tokenizer = Tokenizer.from_file(str(tokenizer_path))
        self.tokenizer.no_truncation()
        self.tokenizer.no_padding()
        pad_id = self.tokenizer.token_to_id("<|endoftext|>")
        if pad_id is None:
            raise CoreConfigurationError("Local Qwen3 tokenizer is missing its padding token")
        self.pad_id = pad_id
        # One session per model/configuration and bounded inference prevent CPU oversubscription.
        self.lock = Lock()


@lru_cache(maxsize=2)
def _runtime(model_path: str, tokenizer_path: str, revision: str, threads: int) -> _Runtime:
    return _Runtime(Path(model_path), Path(tokenizer_path), threads)


class OnnxEmbeddingClient:
    def __init__(self, settings: CoreSettings | None = None):
        self.settings = settings or CoreSettings()
        self.root = Path(self.settings.onnx_dir).resolve()
        self._stamps = None
        self._signature = None

    def _artifacts(self) -> tuple:
        try:
            graph_path = self.root / "onnx/model.onnx"
            graph = onnx.load(str(graph_path), load_external_data=False)
            external = {entry.value for tensor in graph.graph.initializer
                        for entry in tensor.external_data if entry.key == "location"}
            if not external:
                raise CoreConfigurationError("Local ONNX graph must reference the bundled model weights")
            paths = {graph_path, self.root / "tokenizer.json", self.root / "tokenizer_config.json",
                     self.root / "config.json", self.root / "modules.json",
                     self.root / "1_Pooling/config.json", self.root / "sentence_bert_config.json",
                     self.root / "config_sentence_transformers.json"}
            paths.update(graph_path.parent / name for name in external)
            result = []
            for path in paths:
                resolved = path.resolve()
                if not resolved.is_relative_to(self.root):
                    raise CoreConfigurationError("ONNX artifact path escapes the model directory")
                info = resolved.stat()
                result.append((resolved.relative_to(self.root).as_posix(), str(resolved),
                               info.st_size, info.st_mtime_ns))
            pooling = json.loads((self.root / "1_Pooling/config.json").read_text(encoding="utf-8"))
            config = json.loads((self.root / "config.json").read_text(encoding="utf-8"))
            prompts = json.loads((self.root / "config_sentence_transformers.json").read_text(encoding="utf-8"))["prompts"]
            if (pooling.get("pooling_mode") != "lasttoken" or pooling.get("embedding_dimension") != 1024
                    or config.get("hidden_size") != 1024 or self.settings.embedding_dimensions != 1024
                    or prompts.get("document") != "" or prompts.get("query") != QUERY_PREFIX):
                raise CoreConfigurationError("Local model pooling, dimensions or query prompt differ from Qwen3 contract")
            return tuple(sorted(result))
        except (OSError, ValueError, KeyError) as error:
            if isinstance(error, CoreConfigurationError):
                raise
            raise CoreConfigurationError("Local ONNX model files are missing or invalid; check ORIONSTACK_ONNX_DIR") from None

    @property
    def signature(self) -> EmbeddingSignature:
        if self._signature is None:
            self._stamps = self._artifacts()
            revision = content_hash(json.dumps({"artifacts": _artifact_digest(self._stamps),
                "query_prefix": QUERY_PREFIX, "max_tokens": self.settings.onnx_max_tokens,
                "special_tokens": True, "padding": "left", "position_ids": "masked_cumsum_v1"}, sort_keys=True))
            self._signature = EmbeddingSignature(provider="onnxruntime", model=self.settings.onnx_model,
                revision="sha256:" + revision, dimensions=1024,
                preprocessing="qwen3_last_token_query_instruction_v1")
        return self._signature

    def embed(self, texts: tuple[str, ...]) -> EmbeddingBatch:
        return self._embed(texts, query=False)

    def embed_query(self, text: str) -> EmbeddingBatch:
        return self._embed((text,), query=True)

    def _embed(self, texts: tuple[str, ...], *, query: bool) -> EmbeddingBatch:
        if not texts or len(texts) > 32 or any(not isinstance(t, str) or not t.strip() for t in texts):
            raise ValueError("Embedding requires between 1 and 32 nonblank texts")
        signature = self.signature
        for _, path, size, modified in self._stamps:
            info = Path(path).stat()
            if info.st_size != size or info.st_mtime_ns != modified:
                raise CoreConfigurationError("Local ONNX artifacts changed; recreate the embedding client")
        try:
            with _RUNTIME_LOCK:
                runtime = _runtime(str(self.root / "onnx/model.onnx"), str(self.root / "tokenizer.json"),
                                   signature.revision, self.settings.onnx_threads)
            with runtime.lock:
                inputs = tuple(QUERY_PREFIX + text if query else text for text in texts)
                encodings = runtime.tokenizer.encode_batch(list(inputs), add_special_tokens=True)
                length = max(len(e.ids) for e in encodings)
                if length > self.settings.onnx_max_tokens:
                    raise ValueError("Input exceeds ORIONSTACK_ONNX_MAX_TOKENS; silent truncation is forbidden")
                ids = np.full((len(texts), length), runtime.pad_id, dtype=np.int64)
                mask = np.zeros_like(ids)
                for index, encoding in enumerate(encodings):
                    ids[index, -len(encoding.ids):] = encoding.ids
                    mask[index, -len(encoding.ids):] = 1
                positions = np.maximum(np.cumsum(mask, axis=1) - 1, 0).astype(np.int64)
                hidden = runtime.session.run(["last_hidden_state"],
                    {"input_ids": ids, "attention_mask": mask, "position_ids": positions})[0]
                if hidden.shape != (len(texts), length, signature.dimensions):
                    raise ValueError("Local ONNX graph returned invalid hidden state dimensions")
                pooled = last_token_pool(hidden, mask)
                vectors = tuple(normalized_vector(row.tolist(), signature.dimensions) for row in pooled)
            return EmbeddingBatch(signature=signature, vectors=vectors,
                                  input_hashes=tuple(content_hash(text) for text in texts))
        except (ort.capi.onnxruntime_pybind11_state.Fail, ort.capi.onnxruntime_pybind11_state.InvalidArgument,
                ort.capi.onnxruntime_pybind11_state.RuntimeException):
            raise ProviderError("onnxruntime", "local_inference_failed") from None
