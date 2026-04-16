import argparse
import os
import subprocess
import sys
import time
import urllib.request


def wait_backend_ready(port: int, timeout_seconds: int) -> None:
    deadline = time.time() + timeout_seconds
    health_url = f"http://127.0.0.1:{port}/healthz"

    while time.time() < deadline:
        try:
            response = urllib.request.urlopen(health_url, timeout=2)
            body = response.read().decode("utf-8")
            if '"ok"' in body or '"status"' in body:
                print(f"[orionstack] backend ready: {health_url}")
                return
        except Exception:
            pass
        time.sleep(0.75)

    print(
        f"[orionstack] Timed out waiting for backend readiness at {health_url}",
        file=sys.stderr,
    )
    sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Start demo (backend + frontend)")
    parser.add_argument("--app-mode", default="demo", choices=["demo", "dev", "prod"])
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--install-frontend", action="store_true")
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    backend_script = os.path.join(repo_root, "scripts", "dev-backend.py")
    frontend_script = os.path.join(repo_root, "scripts", "dev-frontend.py")
    backend_origin = f"http://127.0.0.1:{args.port}"

    print(f"[orionstack] demo mode boot")
    print(f"[orionstack] app mode      : {args.app_mode}")

    if args.check_only:
        subprocess.run(
            [
                sys.executable,
                backend_script,
                "--app-mode",
                args.app_mode,
                "--host",
                "127.0.0.1",
                "--port",
                str(args.port),
                "--check-only",
            ],
            check=True,
        )
        frontend_cmd = [
            sys.executable,
            frontend_script,
            "--backend-origin",
            backend_origin,
            "--check-only",
        ]
        if args.install_frontend:
            frontend_cmd.append("--install")
        subprocess.run(frontend_cmd, check=True)
        print("[orionstack] demo check only passed.")
        return

    backend_cmd = [
        sys.executable,
        backend_script,
        "--app-mode",
        args.app_mode,
        "--host",
        "127.0.0.1",
        "--port",
        str(args.port),
    ]
    backend_process = subprocess.Popen(backend_cmd)

    wait_backend_ready(args.port, args.timeout)

    frontend_cmd = [sys.executable, frontend_script, "--backend-origin", backend_origin]
    if args.install_frontend:
        frontend_cmd.append("--install")
    frontend_process = subprocess.Popen(frontend_cmd)

    print("[orionstack] frontend started.")

    try:
        backend_process.wait()
    except KeyboardInterrupt:
        backend_process.terminate()
        frontend_process.terminate()
        backend_process.wait()
        frontend_process.wait()


if __name__ == "__main__":
    main()
