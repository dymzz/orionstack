import argparse
import hashlib
import json
import os
import tarfile
from datetime import datetime, timezone
from pathlib import Path


STORAGE_DIRS = [
    "action_links",
    "chat_records",
    "chunks",
    "cleanup_tasks",
    "documents",
    "dynamic_queries",
    "extraction_candidates",
    "extracted_faqs",
    "extraction_tasks",
    "feedback",
    "hard_cases",
    "import_batches",
    "retrieval_traces",
    "source_records",
    "uploads",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Back up OrionStack local storage")
    parser.add_argument("--storage-root", default=None)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--no-uploads", action="store_true")
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    storage_root = Path(args.storage_root) if args.storage_root else repo_root / "backend" / "app" / "storage"
    output_dir = Path(args.output_dir) if args.output_dir else repo_root / "backups"
    included_dirs = [item for item in STORAGE_DIRS if item != "uploads" or not args.no_uploads]

    files = collect_files(storage_root, included_dirs)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = output_dir / f"orionstack-storage-{timestamp}.tar.gz"
    manifest = build_manifest(storage_root, files, included_dirs)

    print("[orionstack] storage backup")
    print(f"[orionstack] storage root : {storage_root}")
    print(f"[orionstack] output       : {backup_path}")
    print(f"[orionstack] files        : {len(files)}")
    print(f"[orionstack] bytes        : {sum(item['size_bytes'] for item in files)}")

    if args.check_only:
        print("[orionstack] backup check only passed.")
        return

    output_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(backup_path, "w:gz") as archive:
        for item in files:
            archive.add(item["absolute_path"], arcname=item["archive_path"])
        manifest_bytes = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
        tar_info = tarfile.TarInfo("manifest.json")
        tar_info.size = len(manifest_bytes)
        archive.addfile(tar_info, fileobj=BytesReader(manifest_bytes))

    print(f"[orionstack] backup written: {backup_path}")


def collect_files(storage_root: Path, included_dirs: list[str]) -> list[dict]:
    files: list[dict] = []
    for dirname in included_dirs:
        directory = storage_root / dirname
        if not directory.exists():
            continue
        for path in sorted(item for item in directory.rglob("*") if item.is_file()):
            relative_path = path.relative_to(storage_root).as_posix()
            files.append(
                {
                    "absolute_path": path,
                    "relative_path": relative_path,
                    "archive_path": f"storage/{relative_path}",
                    "size_bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    return files


def build_manifest(storage_root: Path, files: list[dict], included_dirs: list[str]) -> dict:
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "storage_root": str(storage_root),
        "included_dirs": included_dirs,
        "file_count": len(files),
        "size_bytes": sum(item["size_bytes"] for item in files),
        "files": [
            {
                "path": item["relative_path"],
                "size_bytes": item["size_bytes"],
                "sha256": item["sha256"],
            }
            for item in files
        ],
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class BytesReader:
    def __init__(self, data: bytes) -> None:
        self._data = data
        self._offset = 0

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            size = len(self._data) - self._offset
        chunk = self._data[self._offset : self._offset + size]
        self._offset += len(chunk)
        return chunk


if __name__ == "__main__":
    main()
