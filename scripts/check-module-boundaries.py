"""Reject cross-module private imports in the active modular frontend."""

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1] / "frontend/src"
MODULES = ROOT / "modules"
violations = []
count = 0
for area in (MODULES,ROOT / "compositions",ROOT / "shared"):
    for path in area.rglob("*"):
        if path.suffix not in (".ts",".vue"): continue
        count += 1
        own = path.relative_to(MODULES).parts[0] if path.is_relative_to(MODULES) else None
        for relative in re.findall(r"(?:from\s+|import\s*\()['\"]([^'\"]+)['\"]",path.read_text(encoding="utf-8")):
            if not relative.startswith("."): continue
            target = (path.parent / relative).resolve()
            if target.is_relative_to(MODULES):
                parts = target.relative_to(MODULES).parts
                if parts[0] != own and (len(parts) != 1 and parts[1:] != ("index",)):
                    violations.append(f"{path.relative_to(ROOT)} imports another module's private implementation: {relative}")
            elif own and not target.is_relative_to(ROOT / "shared"):
                violations.append(f"{path.relative_to(ROOT)} imports legacy/nonpublic code: {relative}")
for name in ("account","qa","data-ops","logs"):
    if not (MODULES / name / "index.ts").is_file(): violations.append(f"Missing public facade: {name}")
if violations: raise SystemExit("\n".join(violations))
print(f"Module boundaries checked across {count} active frontend files")
