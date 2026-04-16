from app.routing.contracts import IntentDecision
from app.routing.rule_parser import RuleParser


class RouteResolver:
    def __init__(self) -> None:
        self._rule_parser = RuleParser()

    def resolve(self, raw_query: str) -> IntentDecision:
        return self._rule_parser.parse(raw_query)
