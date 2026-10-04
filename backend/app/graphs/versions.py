"""Small reproducibility fingerprints, with no secret or document content."""
from pathlib import Path
import json
from importlib.metadata import version
from app.knowledge.contracts import content_hash


def conversation_versions(settings,policy_version):
    root=Path(__file__).parent
    code={p.name:content_hash(p.read_bytes()) for p in root.glob('*.py')}
    configuration={'judge':settings.chat_judge,'deepseek_model':settings.deepseek_model,
        'jev_model':settings.jev_model,'provider_timeout':settings.provider_timeout_seconds,
        'context_tokens_approx':3000,'context_chars':12000,'max_history_messages':10,
        'retry_max_attempts':2,'node_run_timeout':120,'workflow_execution':False}
    return {'schema_version':'conversation_v1','graph_fingerprint':content_hash(json.dumps(code,sort_keys=True)),
        'configuration_fingerprint':content_hash(json.dumps(configuration,sort_keys=True)),
        'policy_bundle_version':policy_version,'langgraph':version('langgraph'),
        'checkpoint_postgres':version('langgraph-checkpoint-postgres'),'langchain_postgres':version('langchain-postgres')}
