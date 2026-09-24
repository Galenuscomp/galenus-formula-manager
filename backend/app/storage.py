"""Content-addressed file storage on the local volume."""

import hashlib
from pathlib import Path

from app.config import get_settings


class InvalidFile(ValueError):
    pass


def _path_for(sha256: str) -> Path:
    return get_settings().files_dir / sha256[:2] / f"{sha256}.pdf"


def store_pdf(data: bytes) -> tuple[str, int]:
    if not data.startswith(b"%PDF-"):
        raise InvalidFile("File is not a PDF")
    limit = get_settings().max_upload_mb * 1024 * 1024
    if len(data) > limit:
        raise InvalidFile(f"PDF exceeds {get_settings().max_upload_mb} MB")
    sha = hashlib.sha256(data).hexdigest()
    path = _path_for(sha)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(data)
        tmp.replace(path)
    return sha, len(data)


def read_pdf(sha256: str) -> bytes:
    return _path_for(sha256).read_bytes()


def pdf_path(sha256: str) -> Path:
    return _path_for(sha256)
