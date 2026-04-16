from typing import Literal

from pydantic import BaseModel


class IntentDecision(BaseModel):
    route: Literal["faq_qa", "fallback"]
    confidence: float
    query_for_search: str
