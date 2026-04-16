import argparse
import os
import shutil
import subprocess
import sys


def main() -> None:
    parser = argparse.ArgumentParser(description="Start frontend dev server")
    parser.add_argument("--install", action="store_true")
    parser.add_argument("--backend-origin", default="http://127.0.0.1:8000")
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    frontend_root = os.path.join(repo_root, "frontend")
    node_modules = os.path.join(frontend_root, "node_modules")
    lock_file = os.path.join(frontend_root, "package-lock.json")

    npm_command = shutil.which("npm")
    if not npm_command:
        print("[orionstack] npm not found. Install Node.js first.", file=sys.stderr)
        sys.exit(1)

    should_install = args.install or not os.path.isdir(node_modules)
    if should_install:
        install_mode = "npm ci" if os.path.isfile(lock_file) else "npm install"
    else:
        install_mode = "skip"

    print(f"[orionstack] frontend root: {frontend_root}")
    print(f"[orionstack] dependency step: {install_mode}")
    print(f"[orionstack] backend origin : {args.backend_origin}")

    if args.check_only:
        print("[orionstack] frontend check only passed.")
        return

    env = os.environ.copy()
    env["ORIONSTACK_BACKEND_ORIGIN"] = args.backend_origin

    if should_install:
        subprocess.run(
            [npm_command, "ci" if install_mode == "npm ci" else "install"],
            cwd=frontend_root,
            check=True,
        )
    else:
        print("[orionstack] node_modules already present, skipping dependency install.")

    os.chdir(frontend_root)
    subprocess.run([npm_command, "run", "dev"], env=env)


if __name__ == "__main__":
    main()
