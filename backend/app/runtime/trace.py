from uuid import uuid4

from app.observability.logging import trace_id_ctx


def new_trace_id() -> str:
    trace_id = uuid4().hex
    trace_id_ctx.set(trace_id)
    return trace_id


def set_trace_id(trace_id: str) -> None:
    trace_id_ctx.set(trace_id)


def get_trace_id() -> str:
    return trace_id_ctx.get("")