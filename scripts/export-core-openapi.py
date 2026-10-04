"""Export only the active core HTTP contract without starting providers or a DB."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT / "backend"))


def core_schema():
    from main import app
    schema = app.openapi()
    paths = {path:value for path,value in schema["paths"].items()
             if path in ("/api/query","/api/chat","/api/feedback","/api/access-context") or path.startswith(("/api/chat/","/api/query-runs","/api/retrieval-events/","/api/workbench/","/api/documents","/api/auth/","/api/assets/","/api/backups","/api/dataops/","/api/support/"))}
    needed = set()
    def refs(value):
        if isinstance(value,dict):
            for key,child in value.items():
                if key == "$ref" and child.startswith("#/components/schemas/"):
                    needed.add(child.rsplit("/",1)[-1])
                else: refs(child)
        elif isinstance(value,list):
            for child in value: refs(child)
    refs(paths)
    scanned = set()
    while needed - scanned:
        name = next(iter(needed - scanned)); scanned.add(name)
        refs(schema["components"]["schemas"][name])
    return {"openapi":schema["openapi"],"info":schema["info"],"paths":paths,
            "components":{"schemas":{name:schema["components"]["schemas"][name] for name in sorted(needed)},
                          "securitySchemes":schema["components"].get("securitySchemes",{})}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--check",action="store_true")
    args = parser.parse_args()
    path = ROOT / "docs/designs/core_knowledge.openapi.json"
    schema = core_schema()
    if args.check:
        if json.loads(path.read_text(encoding="utf-8")) != schema:
            raise SystemExit("Core OpenAPI artifact is stale")
        print("Core OpenAPI artifact matches the runtime contract")
    else:
        path.write_text(json.dumps(schema,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print("Updated docs/designs/core_knowledge.openapi.json")
