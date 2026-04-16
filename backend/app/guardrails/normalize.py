import re


def normalize_query(raw_query: str) -> str:
    value = re.sub(r"\s+", " ", raw_query).strip()
    return value
