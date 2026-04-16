import argparse
import os
import sys


def get_record_summary(path: str) -> dict:
    if not os.path.isfile(path):
        return {"exists": False, "lines": 0, "size_bytes": 0}
    with open(path, encoding="utf-8") as f:
        lines = sum(1 for _ in f)
    size_bytes = os.path.getsize(path)
    return {"exists": True, "lines": lines, "size_bytes": size_bytes}


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean local record files")
    parser.add_argument("--chat-only", action="store_true")
    parser.add_argument("--feedback-only", action="store_true")
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument(
        "--what-if",
        action="store_true",
        help="Preview what would be deleted without deleting",
    )
    args = parser.parse_args()

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    targets = [
        {
            "name": "chat records",
            "path": os.path.join(
                repo_root,
                "backend",
                "app",
                "storage",
                "chat_records",
                "chat_records.jsonl",
            ),
        },
        {
            "name": "feedback records",
            "path": os.path.join(
                repo_root,
                "backend",
                "app",
                "storage",
                "feedback",
                "feedback_records.jsonl",
            ),
        },
    ]

    if args.chat_only and not args.feedback_only:
        targets = [t for t in targets if t["name"] == "chat records"]
    elif args.feedback_only and not args.chat_only:
        targets = [t for t in targets if t["name"] == "feedback records"]

    print("[orionstack] local record maintenance")

    for target in targets:
        summary = get_record_summary(target["path"])
        if summary["exists"]:
            print(f"[orionstack] {target['name']}: {target['path']}")
            print(
                f"[orionstack]   lines={summary['lines']} size_bytes={summary['size_bytes']}"
            )
        else:
            print(f"[orionstack] {target['name']}: missing ({target['path']})")

    if args.check_only:
        print("[orionstack] check only passed.")
        return

    existing = [t for t in targets if get_record_summary(t["path"])["exists"]]
    if not existing:
        print("[orionstack] no local record files to clean.")
        return

    for target in existing:
        if args.what_if:
            print(f"[orionstack] would remove: {target['path']}")
        else:
            os.remove(target["path"])
            print(f"[orionstack] removed: {target['path']}")

    if not args.what_if:
        print("[orionstack] local record cleanup complete.")


if __name__ == "__main__":
    main()
