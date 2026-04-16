import argparse
import os
import shutil
import subprocess
import sys


def main() -> None:
    parser = argparse.ArgumentParser(description="Start backend in production mode")
    parser.add_argument("--app-mode", default="prod", choices=["demo", "dev", "prod"])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    backend_root = os.path.join(repo_root, "backend")
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

    print(f"[orionstack] start-backend mode: {args.app_mode}")
    print(f"[orionstack] start-backend host : {args.host}:{args.port}")
    print(f"[orionstack] start-backend workers: {args.workers}")
    print(f"[orionstack] start-backend python: {python_command}")

    if args.check_only:
        print("[orionstack] start-backend check only passed.")
        return

    env = os.environ.copy()
    env["ORIONSTACK_APP_MODE"] = args.app_mode
    env["ORIONSTACK_HOST"] = args.host
    env["ORIONSTACK_PORT"] = str(args.port)

    os.chdir(backend_root)
    subprocess.run(
        [
            python_command,
            "-m",
            "uvicorn",
            "main:app",
            "--host",
            args.host,
            "--port",
            str(args.port),
            "--workers",
            str(args.workers),
        ],
        env=env,
    )


if __name__ == "__main__":
    main()
