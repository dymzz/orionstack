import argparse
import os
import re
import subprocess
import sys


def invoke_git(*args: str) -> list[str]:
    result = subprocess.run(["git"] + list(args), capture_output=True, text=True)
    if result.returncode != 0:
        output = result.stderr.strip() or result.stdout.strip() or "<no output>"
        print(f"[orionstack] git {' '.join(args)} failed.\n{output}", file=sys.stderr)
        sys.exit(1)
    lines = result.stdout.strip().splitlines()
    return lines


def get_pyproject_version(pyproject_path: str) -> tuple[str, str]:
    with open(pyproject_path, encoding="utf-8") as f:
        content = f.read()
    match = re.search(r'^version\s*=\s*"([^"]+)"\s*$', content, re.MULTILINE)
    if not match:
        print(
            "[orionstack] Could not find [project].version in pyproject.toml",
            file=sys.stderr,
        )
        sys.exit(1)
    return content, match.group(1)


def set_pyproject_version(pyproject_path: str, target_version: str) -> str:
    content, current_version = get_pyproject_version(pyproject_path)
    if current_version == target_version:
        return current_version
    updated = re.sub(
        r'^version\s*=\s*"[^"]+"\s*$',
        f'version = "{target_version}"',
        content,
        count=1,
        flags=re.MULTILINE,
    )
    with open(pyproject_path, "w", encoding="utf-8") as f:
        f.write(updated)
    return current_version


def normalize_version(raw_version: str, tag_prefix: str) -> str:
    value = raw_version.strip()
    if not value:
        print("[orionstack] Version cannot be empty.", file=sys.stderr)
        sys.exit(1)
    if tag_prefix and value.startswith(tag_prefix):
        value = value[len(tag_prefix) :]
    if not re.match(r"^\d+\.\d+\.\d+([.\-][0-9A-Za-z]+)*$", value):
        print("[orionstack] Version must look like 0.1.3 or 0.1.3-rc1", file=sys.stderr)
        sys.exit(1)
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description="Interactive version release script")
    parser.add_argument("--version", default=None)
    parser.add_argument("--commit-message", default=None)
    parser.add_argument("--tag-prefix", default="v")
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--skip-push", action="store_true")
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pyproject_path = os.path.join(repo_root, "pyproject.toml")

    if not os.path.isfile(pyproject_path):
        print(
            f"[orionstack] pyproject.toml not found: {pyproject_path}", file=sys.stderr
        )
        sys.exit(1)

    _, current_version = get_pyproject_version(pyproject_path)
    current_branch = invoke_git("rev-parse", "--abbrev-ref", "HEAD")[0].strip()

    if current_branch == "HEAD":
        print(
            "[orionstack] Detached HEAD is not supported. Checkout a branch first.",
            file=sys.stderr,
        )
        sys.exit(1)

    target_version_str = args.version
    if not target_version_str:
        target_version_str = input(
            f"Enter release version (current: {current_version}): "
        ).strip()
    target_version = normalize_version(target_version_str, args.tag_prefix)
    tag_name = (
        f"{args.tag_prefix}{target_version}" if args.tag_prefix else target_version
    )

    commit_message = args.commit_message
    if not commit_message:
        commit_message = input("Enter commit message: ").strip()

    existing_tags = invoke_git("tag", "--list", tag_name)
    if existing_tags and existing_tags[0].strip() == tag_name:
        print(f"[orionstack] Tag already exists: {tag_name}", file=sys.stderr)
        sys.exit(1)

    if not args.skip_push:
        invoke_git("remote", "get-url", args.remote)

    print("[orionstack] release summary")
    print(f"[orionstack] branch         : {current_branch}")
    print(f"[orionstack] current version: {current_version}")
    print(f"[orionstack] target version : {target_version}")
    print(f"[orionstack] tag            : {tag_name}")
    print(f"[orionstack] commit message : {commit_message}")
    print(f"[orionstack] push enabled   : {not args.skip_push}")

    if args.check_only:
        print("[orionstack] check only passed.")
        return

    confirmation = (
        input("Continue with git add/commit/tag/push? (y/N): ").strip().lower()
    )
    if confirmation not in ("y", "yes"):
        print("[orionstack] Release cancelled by user.", file=sys.stderr)
        sys.exit(1)

    previous_version = set_pyproject_version(pyproject_path, target_version)
    if previous_version != target_version:
        print(
            f"[orionstack] updated pyproject version: {previous_version} -> {target_version}"
        )
    else:
        print(f"[orionstack] pyproject version already at {target_version}")

    status_lines = invoke_git("status", "--porcelain")
    if not status_lines:
        print(
            "[orionstack] No changes to commit. Update files or choose a new version first.",
            file=sys.stderr,
        )
        sys.exit(1)

    invoke_git("add", "--all")
    invoke_git("commit", "-m", commit_message)
    invoke_git("tag", "-a", tag_name, "-m", f"release {tag_name}")

    if not args.skip_push:
        invoke_git("push", args.remote, current_branch)
        invoke_git("push", args.remote, tag_name)
        print(f"[orionstack] pushed branch and tag to {args.remote}")
    else:
        print("[orionstack] SkipPush enabled. Branch and tag remain local only.")

    print(f"[orionstack] release complete: {tag_name}")


if __name__ == "__main__":
    main()
