from uuid import uuid4


def new_trace_id() -> str:
    return uuid4().hex
