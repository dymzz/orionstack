"""Configuration check; explicit flags make a tiny synthetic live API request."""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.config.core_settings import CoreConfigurationError, CoreSettings
from app.decision.deepseek import DeepSeekClient
from app.decision.jev import JevClient
from app.decision.providers import ProviderError
from app.knowledge.contracts import AccessContext, EvidenceCandidate, QueryContext, SourceRef


def main() -> int:
    parser = argparse.ArgumentParser(description="Check core environment or explicitly smoke-test providers")
    parser.add_argument("--live-jev", action="store_true")
    parser.add_argument("--live-deepseek", action="store_true")
    args = parser.parse_args()
    settings = CoreSettings()
    report = settings.configuration_status()
    try:
        if args.live_jev:
            decision = JevClient(settings).decide(QueryContext(query="What is the exact due date of invoice INV-DEMO-001?"))
            report["jev"] = {"model": decision.model, "strategy": decision.strategy,
                             "usage": decision.usage.model_dump()}
        if args.live_deepseek:
            evidence = EvidenceCandidate(
                evidence_id="demo-evidence-1", evidence_kind="structured_record", tenant_id="demo",
                access_scope="internal", source=SourceRef(source_id="synthetic-invoice", source_version="1",
                                                           source_locator="demo://invoices/INV-DEMO-001"),
                text="Invoice INV-DEMO-001 is due on 2026-10-15.",
                typed_values={"due_date": "2026-10-15"}, retrieval_method="synthetic_smoke",
            )
            answer = DeepSeekClient(settings).generate(
                QueryContext(query="When is invoice INV-DEMO-001 due?"), (evidence,),
                AccessContext(tenant_id="demo", user_id="smoke-test"),
            )
            if (answer.status != "answered" or len(answer.citations) != 1
                    or answer.citations[0].evidence_id != "demo-evidence-1" or "2026-10-15" not in answer.answer):
                raise ProviderError("deepseek", "synthetic_answer_check_failed")
            report["deepseek"] = {"model": answer.model, "status": answer.status,
                                  "citation_count": len(answer.citations),
                                  "usage": answer.usage.model_dump() if answer.usage else None}
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except (CoreConfigurationError, ProviderError) as error:
        print(f"[orionstack] {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
