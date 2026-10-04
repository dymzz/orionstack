"""psycopg async connections require a Selector loop on Windows."""
import asyncio
import sys


def create_loop():
    return asyncio.SelectorEventLoop() if sys.platform=='win32' else asyncio.new_event_loop()
