import argparse
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass


PHASE2_TEST_FILES = [
    "backend/tests/test_phase2_retrieval.py",
    "backend/tests/test_chat_flow.py",
    "backend/tests/test_phase2_trace.py",
    "backend/tests/test_phase2_hard_cases.py",
]

QUICK_EXTRA_TEST_FILES = [
    "backend/tests/test_auth.py",
    "backend/tests/test_phase2_settings.py",
    "backend/tests/test_knowledge_publication.py",
    "backend/tests/test_storage_backup.py",
    "backend/tests/test_core_providers.py",
    "backend/tests/test_postgres_migration.py",
    "backend/tests/test_raw_retrieval.py",
    "backend/tests/test_raw_postgres_integration.py",
    "backend/tests/test_p0_core.py",
    "backend/tests/test_p0_fail_closed.py",
    "backend/tests/test_p0_query_acceptance.py",
    "backend/tests/test_benchmark_ingestion.py",
    "backend/tests/test_onnx_embedding.py",
    "backend/tests/test_p1_evidence.py",
    "backend/tests/test_identity_boundary.py",
    "backend/tests/test_security_boundary.py",
    "backend/tests/test_dataops_assets.py",
]


@dataclass(frozen=True)
class CheckStep:
    name: str
    command: list[str]
    cwd: str
    env: dict[str, str] | None = None
    hide_output: bool = False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run release checks for backend, frontend, and production compose"
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="run targeted backend checks instead of the full backend test suite",
    )
    parser.add_argument("--skip-backend", action="store_true")
    parser.add_argument("--skip-frontend", action="store_true")
    parser.add_argument("--skip-compose", action="store_true")
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    frontend_root = os.path.join(repo_root, "frontend")
    python_command = resolve_python(repo_root)
    npm_command = resolve_tool("npm")
    docker_command = resolve_tool("docker")

    steps: list[CheckStep] = []
    if not args.skip_backend:
        backend_command = [python_command, "-m", "pytest"]
        if args.quick:
            backend_command.extend([*PHASE2_TEST_FILES, *QUICK_EXTRA_TEST_FILES])
        else:
            backend_command.append("backend/tests")
        backend_command.append("-q")
        steps.append(CheckStep("backend tests", backend_command, repo_root))
        for script in ("export-core-openapi.py", "export-evidence-example.py"):
            steps.append(CheckStep(script, [python_command, "scripts/"+script, "--check"], repo_root))
        steps.append(CheckStep("module boundaries", [python_command, "scripts/check-module-boundaries.py"], repo_root))
        steps.append(
            CheckStep(
                "storage backup dry-run",
                [python_command, "scripts/backup-storage.py", "--check-only"],
                repo_root,
            )
        )

    if not args.skip_frontend:
        if npm_command is None:
            fail("npm not found. Install Node.js or use --skip-frontend.")
        steps.append(CheckStep("frontend build", [npm_command, "run", "build"], frontend_root))

    if not args.skip_compose:
        if docker_command is None:
            fail("docker not found. Install Docker or use --skip-compose.")
        steps.append(
            CheckStep(
                "production compose config",
                [
                    docker_command,
                    "compose",
                    "--env-file",
                    ".env.prod.example",
                    "-f",
                    "docker-compose.prod.yml",
                    "config",
                ],
                repo_root,
                env=sanitized_compose_env(),
                hide_output=True,
            )
        )

    log("[orionstack] release check")
    log(f"[orionstack] python: {python_command}")
    log(f"[orionstack] mode  : {'quick' if args.quick else 'full'}")
    for step in steps:
        log(f"[orionstack] step  : {step.name}")
        log(f"[orionstack] cmd   : {' '.join(step.command)}")

    if args.check_only:
        log("[orionstack] release check dry-run passed.")
        return

    for step in steps:
        run_step(step)

    log("[orionstack] release check passed.")


def resolve_python(repo_root: str) -> str:
    venv_python = os.path.join(repo_root, ".venv", "Scripts", "python.exe")
    if os.path.isfile(venv_python):
        return venv_python
    python_command = shutil.which("python")
    if python_command is None:
        fail("Python not found. Activate the project environment or install Python first.")
    return python_command


def resolve_tool(name: str) -> str | None:
    resolved = shutil.which(name)
    if resolved is not None:
        return resolved
    if os.name == "nt":
        return shutil.which(f"{name}.cmd") or shutil.which(f"{name}.exe")
    return None


def run_step(step: CheckStep) -> None:
    log(f"[orionstack] running: {step.name}")
    if step.hide_output:
        completed = subprocess.run(
            step.command,
            cwd=step.cwd,
            env=step.env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if completed.returncode != 0:
            print(completed.stderr, file=sys.stderr)
            raise SystemExit(completed.returncode)
        return

    completed = subprocess.run(step.command, cwd=step.cwd, env=step.env)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def sanitized_compose_env() -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "DASHSCOPE_API_KEY": "",
            "QWEN_API_KEY": "",
            "ORIONSTACK_QWEN_API_KEY": "",
            "ORIONSTACK_PLANNER_API_KEY": "",
            "ORIONSTACK_EXTRACTION_API_KEY": "",
            "TYPESAFE_API_KEY": "",
            "DEEPSEEK_API_KEY": "",
            "CF_API_TOKEN": "",
            "CF_ACCOUNT_ID": "",
            "ORIONSTACK_DATABASE_URL": "",
            "ORIONSTACK_OIDC_CLIENT_SECRET": "",
            "ORIONSTACK_ADMIN_PASSWORD": "replace-with-a-strong-password",
            "ORIONSTACK_ADMIN_TOKEN_SECRET": "replace-with-at-least-24-random-characters",
        }
    )
    return env


def fail(message: str) -> None:
    print(f"[orionstack] {message}", file=sys.stderr)
    raise SystemExit(1)


def log(message: str) -> None:
    print(message, flush=True)


if __name__ == "__main__":
    main()
