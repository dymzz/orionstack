"""Initialize LangGraph's own checkpoint tables once, in their dedicated schema."""
import argparse
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.config.core_settings import CoreSettings,CoreConfigurationError
from app.knowledge.postgres import DatabaseUnavailable


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    if not args.apply:
        print('Preview: LangGraph PostgresSaver.setup() in conversation_checkpoint; apply Alembic 011 first.');return 0
    import psycopg
    from psycopg.rows import dict_row
    from langgraph.checkpoint.postgres import PostgresSaver
    try:
        with psycopg.connect(CoreSettings().require_database_url(),autocommit=True,prepare_threshold=0,
                row_factory=dict_row,options='-c search_path=conversation_checkpoint,pg_catalog,public') as connection:
            row=connection.execute("SELECT to_regclass('qa.conversation_threads') AS present").fetchone()
            if not row['present']:raise DatabaseUnavailable('Apply Alembic 011 before checkpoint setup')
            connection.execute("SELECT pg_advisory_lock(hashtext('orionstack.checkpoint.setup'))")
            try:PostgresSaver(connection).setup()
            finally:connection.execute("SELECT pg_advisory_unlock(hashtext('orionstack.checkpoint.setup'))")
        print('LangGraph checkpoint tables ready in conversation_checkpoint; no model calls.');return 0
    except (psycopg.Error,CoreConfigurationError,DatabaseUnavailable):
        print('Checkpoint setup failed; inspect database configuration and migration state.',file=sys.stderr);return 2


if __name__=='__main__':raise SystemExit(main())
