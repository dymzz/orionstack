from app.schemas.response import CitationItem


def map_citation(item: dict) -> CitationItem:
    return CitationItem(
        citation_id=item["id"],
        source_label=item.get("source_label", "FAQ"),
        source_locator=item.get("source_locator", item["id"]),
        snippet=item.get("snippet", item.get("question", item.get("answer", ""))),
    )
