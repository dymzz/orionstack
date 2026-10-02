import argparse
import hashlib
import json
import shutil
import tarfile
from pathlib import Path, PurePosixPath, PureWindowsPath


def main() -> None:
    parser = argparse.ArgumentParser(description="Restore an OrionStack storage backup")
    parser.add_argument("backup_path")
    parser.add_argument("--storage-root", default=None)
    parser.add_argument("--what-if", action="store_true")
    parser.add_argument("--confirm-restore", action="store_true")
    args = parser.parse_args()

    if not args.what_if and not args.confirm_restore:
        raise SystemExit(
            "[orionstack] restore is destructive. Pass --what-if to preview or --confirm-restore to apply."
        )

    repo_root = Path(__file__).resolve().parents[1]
    storage_root = Path(args.storage_root) if args.storage_root else repo_root / "backend" / "app" / "storage"
    backup_path = Path(args.backup_path)
    if not backup_path.is_file():
        raise SystemExit(f"[orionstack] backup not found: {backup_path}")

    print("[orionstack] storage restore")
    print(f"[orionstack] backup      : {backup_path}")
    print(f"[orionstack] storage root: {storage_root}")

    with tarfile.open(backup_path, "r:gz") as archive:
        members = [member for member in archive.getmembers() if member.name.startswith("storage/")]
        validate_members(members)
        files = [member for member in members if member.isfile()]
        verify_manifest(archive, files)
        storage_root = storage_root.resolve()
        targets = {}
        for member in files:
            target = storage_root / member.name.removeprefix("storage/")
            if not target.resolve().is_relative_to(storage_root):
                raise SystemExit(f"[orionstack] unsafe restore target: {member.name}")
            targets[member.name] = target
        document_metadata = rebased_document_metadata(archive, storage_root)
        print(f"[orionstack] files       : {len(files)}")

        if args.what_if:
            for member in files:
                target = targets[member.name]
                action = "overwrite" if target.exists() else "create"
                print(f"[orionstack] would {action}: {target}")
            print("[orionstack] restore preview complete.")
            return

        storage_root.mkdir(parents=True, exist_ok=True)
        for member in files:
            target = targets[member.name]
            target.parent.mkdir(parents=True, exist_ok=True)
            if member.name == "storage/documents/documents.jsonl":
                target.write_bytes(document_metadata)
                print(f"[orionstack] restored: {target}")
                continue
            source = archive.extractfile(member)
            if source is None:
                continue
            with source, target.open("wb") as destination:
                shutil.copyfileobj(source, destination)
            print(f"[orionstack] restored: {target}")

    print("[orionstack] storage restore complete.")


def validate_members(members: list[tarfile.TarInfo]) -> None:
    seen: set[str] = set()
    for member in members:
        relative = member.name.removeprefix("storage/")
        parts = PurePosixPath(relative.replace("\\", "/")).parts
        if (
            not relative
            or relative.startswith(("/", "\\"))
            or PureWindowsPath(relative).drive
            or ".." in parts
            or any(":" in part for part in parts)
            or "\\" in relative
            or not (member.isfile() or member.isdir())
            or member.name in seen
        ):
            raise SystemExit(f"[orionstack] unsafe backup path: {member.name}")
        seen.add(member.name)


def verify_manifest(archive: tarfile.TarFile, files: list[tarfile.TarInfo]) -> None:
    manifests = [member for member in archive.getmembers() if member.name == "manifest.json"]
    if len(manifests) != 1 or not manifests[0].isfile():
        raise SystemExit("[orionstack] backup requires a regular manifest.json")
    try:
        with archive.extractfile(manifests[0]) as source:
            manifest = json.load(source)
        entries = {f"storage/{item['path']}": item for item in manifest["files"]}
        if len(entries) != len(manifest["files"]) or manifest["file_count"] != len(files):
            raise ValueError("invalid manifest file count")
        if set(entries) != {member.name for member in files}:
            raise ValueError("manifest file list does not match the archive")
        for member in files:
            entry = entries[member.name]
            if entry["size_bytes"] != member.size:
                raise ValueError(f"size mismatch: {member.name}")
            digest = hashlib.sha256()
            with archive.extractfile(member) as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(chunk)
            if digest.hexdigest() != entry["sha256"]:
                raise ValueError(f"checksum mismatch: {member.name}")
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        raise SystemExit(f"[orionstack] backup integrity check failed: {error}") from error


def rebased_document_metadata(archive: tarfile.TarFile, storage_root: Path) -> bytes | None:
    name = "storage/documents/documents.jsonl"
    if name not in archive.getnames():
        return None
    try:
        with archive.extractfile(name) as source:
            records = [json.loads(line) for line in source.read().decode("utf-8").splitlines() if line.strip()]
        for record in records:
            filename = record["storage_path"].replace("\\", "/").rsplit("/", 1)[-1]
            if not filename or filename in {".", ".."} or ":" in filename:
                raise ValueError("invalid document storage path")
            record["storage_path"] = str(storage_root / "uploads" / filename)
        return ("\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n").encode("utf-8")
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        raise SystemExit(f"[orionstack] invalid document metadata: {error}") from error


if __name__ == "__main__":
    main()
