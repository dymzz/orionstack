import importlib.util
from io import BytesIO
import json
from pathlib import Path
import sys
import tarfile

import pytest

from app.extract.candidate_reviewer import publish_candidate
from app.storage.repositories.cleanup_task_repo import CleanupTaskRepo
from app.storage.repositories.extracted_faq_repo import ExtractedFaqRepo
from app.storage.repositories.extraction_candidate_repo import ExtractionCandidateRepo
from app.storage.repositories.extraction_task_repo import ExtractionTaskRepo
from app.storage.repositories.source_record_repo import SourceRecordRepo
from test_extraction import _make_candidate, _make_source_record


def load_script(name):
    path = Path(__file__).resolve().parents[2] / "scripts" / name
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


backup = load_script("backup-storage.py")
restore = load_script("restore-storage.py")


def run_script(monkeypatch, module, *args):
    monkeypatch.setattr(sys, "argv", [module.__file__, *map(str, args)])
    module.main()


def make_backup(monkeypatch, tmp_path):
    source = tmp_path / "source"
    source_repo = SourceRecordRepo(storage_dir=source / "source_records")
    source_record = _make_source_record()
    source_repo.upsert(source_record)
    candidates = ExtractionCandidateRepo(storage_dir=source / "extraction_candidates")
    candidate = _make_candidate(review_status="approved")
    candidates.create(candidate)
    faq_repo = ExtractedFaqRepo(storage_dir=source / "extracted_faqs")
    unit = publish_candidate(candidate, source_record, extracted_faq_repo=faq_repo)
    task = ExtractionTaskRepo(storage_dir=source / "extraction_tasks").enqueue_for_source_record(
        source_record, reason="backup-test"
    )
    cleanup = CleanupTaskRepo(storage_dir=source / "cleanup_tasks").enqueue_for_source_record(
        source_record, reason="backup-test"
    )
    for dirname in ("import_batches", "chat_records", "feedback", "retrieval_traces", "hard_cases", "action_links", "dynamic_queries", "chunks"):
        directory = source / dirname
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "records.jsonl").write_text(json.dumps({"directory": dirname}) + "\n", encoding="utf-8")
    uploads = source / "uploads"
    uploads.mkdir()
    (uploads / "doc-backup_guide.txt").write_bytes("恢复后的文档。".encode())
    documents = source / "documents"
    documents.mkdir()
    (documents / "documents.jsonl").write_text(json.dumps({
        "document_id": "doc-backup",
        "filename": "guide.txt",
        "storage_path": r"D:\old-machine\storage\uploads\doc-backup_guide.txt",
    }) + "\n", encoding="utf-8")
    run_script(monkeypatch, backup, "--storage-root", source, "--output-dir", tmp_path / "backups")
    archive = next((tmp_path / "backups").glob("*.tar.gz"))
    return source, archive, source_record, candidate, unit, task, cleanup


def test_backup_restore_preserves_knowledge_provenance_and_task_state(monkeypatch, tmp_path):
    source, archive, record, candidate, unit, task, cleanup = make_backup(monkeypatch, tmp_path)
    target = tmp_path / "restored"
    run_script(monkeypatch, restore, archive, "--storage-root", target, "--confirm-restore")
    for original in source.rglob("*"):
        if original.is_file() and original.name != "documents.jsonl":
            assert (target / original.relative_to(source)).read_bytes() == original.read_bytes()
    assert SourceRecordRepo(storage_dir=target / "source_records").get(record.source_record_id) == record
    assert ExtractionCandidateRepo(storage_dir=target / "extraction_candidates").get(candidate.candidate_id) == candidate
    assert ExtractionTaskRepo(storage_dir=target / "extraction_tasks").get(task.extraction_task_id) == task
    assert CleanupTaskRepo(storage_dir=target / "cleanup_tasks").get(cleanup.cleanup_task_id) == cleanup
    assert ExtractedFaqRepo(storage_dir=target / "extracted_faqs").list_all()[0]["unit_id"] == unit.unit_id
    metadata = json.loads((target / "documents/documents.jsonl").read_text(encoding="utf-8"))
    assert Path(metadata["storage_path"]) == target / "uploads/doc-backup_guide.txt"
    assert Path(metadata["storage_path"]).read_bytes() == (source / "uploads/doc-backup_guide.txt").read_bytes()


def test_restore_preview_verifies_archive_without_writing(monkeypatch, tmp_path):
    _, archive, *_ = make_backup(monkeypatch, tmp_path)
    target = tmp_path / "preview"
    run_script(monkeypatch, restore, archive, "--storage-root", target, "--what-if")
    assert not target.exists()


def test_restore_rejects_corrupt_file_before_writing_anything(monkeypatch, tmp_path):
    _, original, *_ = make_backup(monkeypatch, tmp_path)
    corrupt = tmp_path / "corrupt.tar.gz"
    with tarfile.open(original, "r:gz") as source, tarfile.open(corrupt, "w:gz") as target:
        for member in source.getmembers():
            data = source.extractfile(member).read()
            if member.name == "storage/uploads/doc-backup_guide.txt":
                data = b"X" + data[1:]
            target.addfile(member, BytesIO(data))
    target = tmp_path / "restored"
    with pytest.raises(SystemExit, match="checksum mismatch"):
        run_script(monkeypatch, restore, corrupt, "--storage-root", target, "--confirm-restore")
    assert not target.exists()


@pytest.mark.parametrize("name", ["storage/../escape", r"storage/..\escape", "storage/C:/escape", "storage/file:stream"])
def test_restore_rejects_unsafe_paths(monkeypatch, tmp_path, name):
    archive = tmp_path / "unsafe.tar.gz"
    with tarfile.open(archive, "w:gz") as target:
        item = tarfile.TarInfo(name)
        item.size = 4
        target.addfile(item, BytesIO(b"data"))
    restored = tmp_path / "restored"
    with pytest.raises(SystemExit, match="unsafe backup path"):
        run_script(monkeypatch, restore, archive, "--storage-root", restored, "--confirm-restore")
    assert not restored.exists()


@pytest.mark.parametrize("link_type", [tarfile.SYMTYPE, tarfile.LNKTYPE])
def test_restore_rejects_archive_links(link_type):
    member = tarfile.TarInfo("storage/uploads/link")
    member.type = link_type
    member.linkname = "../outside"
    with pytest.raises(SystemExit, match="unsafe backup path"):
        restore.validate_members([member])
