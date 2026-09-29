"""Content-addressed file storage on the local volume."""

import hashlib
import io
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


MAX_LOGO_BYTES = 1024 * 1024
LOGO_TYPES = {"png": "image/png", "jpeg": "image/jpeg"}


def _image_path(sha256: str, kind: str) -> Path:
    return get_settings().files_dir / "images" / f"{sha256}.{kind}"


def store_logo(data: bytes) -> tuple[str, str]:
    """Validate and store a PNG or JPEG logo; returns (sha256, "png" | "jpeg")."""
    if len(data) > MAX_LOGO_BYTES:
        raise InvalidFile("The logo must be 1 MB or smaller")
    from PIL import Image, UnidentifiedImageError

    try:
        with Image.open(io.BytesIO(data)) as img:
            kind = (img.format or "").lower()
            img.verify()
            size = img.size
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise InvalidFile("The logo must be a PNG or JPEG image") from exc
    if kind not in LOGO_TYPES:
        raise InvalidFile("The logo must be a PNG or JPEG image")
    if max(size) > 4000:
        raise InvalidFile("The logo is too large; use an image under 4000 pixels wide")
    sha = hashlib.sha256(data).hexdigest()
    path = _image_path(sha, kind)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return sha, kind


def logo_path(sha256: str, kind: str) -> Path:
    return _image_path(sha256, kind)


def read_pdf(sha256: str) -> bytes:
    return _path_for(sha256).read_bytes()


def pdf_path(sha256: str) -> Path:
    return _path_for(sha256)
