import argparse
import os
import shutil
import subprocess
import sys


PHASE2_TEST_FILES = [
    "backend/tests/test_phase2_retrieval.py",
    "backend/tests/test_chat_flow.py",
    "backend/tests/test_phase2_trace.py",
    "backend/tests/test_phase2_hard_cases.py",
]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the fixed Phase 2 regression suite"
    )
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument(
        "pytest_args",
        nargs="*",
        help="extra arguments passed through to pytest",
    )
    args = parser.parse_args()

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    venv_python = os.path.join(repo_root, ".venv", "Scripts", "python.exe")

    if os.path.isfile(venv_python):
        python_command = venv_python
    else:
        python_command = shutil.which("python")
        if not python_command:
            print(
                "[orionstack] Python not found. Activate the project environment or install Python first.",
                file=sys.stderr,
            )
            sys.exit(1)

    pytest_command = [python_command, "-m", "pytest", *PHASE2_TEST_FILES, *args.pytest_args]

    print("[orionstack] phase 2 regression suite")
    for test_file in PHASE2_TEST_FILES:
        print(f"[orionstack]   - {test_file}")
    print(f"[orionstack] python: {python_command}")
    print(f"[orionstack] cmd   : {' '.join(pytest_command)}")

    if args.check_only:
        print("[orionstack] phase 2 regression check only passed.")
        return

    os.chdir(repo_root)
    completed = subprocess.run(pytest_command)
    raise SystemExit(completed.returncode)


if __name__ == "__main__":
    main()
