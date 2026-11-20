"""
Upload safety, shared by every file field.

- The *content* is checked (Pillow opens images, PDFs must start with %PDF-); the browser's
  content-type and the file extension are not trusted.
- Only JPEG / PNG / WebP / HEIC-free formats Pillow can verify are accepted as images, so SVG/HTML
  (which could carry scripts) never reach /media/.
- Files are stored under random names: originals can't overwrite each other and links to bills or
  site photos can't be guessed.
"""

import uuid
from pathlib import Path

from django.utils import timezone
from PIL import Image, UnidentifiedImageError

from .exceptions import BusinessRuleError

IMAGE_FORMATS = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp", "GIF": ".gif"}
MAX_IMAGE_MB = 8
MAX_DOCUMENT_MB = 8
MAX_PIXELS = 40_000_000  # ~ 40 MP; blocks "decompression bomb" images


def _size_check(f, max_mb, field):
    if f.size > max_mb * 1024 * 1024:
        raise BusinessRuleError(f"{f.name} is larger than {max_mb} MB.", field=field)


def image_format(f):
    """Return the real image format (JPEG/PNG/…) or None."""
    try:
        f.seek(0)
        with Image.open(f) as img:
            fmt = img.format
            w, h = img.size
            img.verify()
        if w * h > MAX_PIXELS:
            return None
        return fmt if fmt in IMAGE_FORMATS else None
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        return None
    finally:
        f.seek(0)


def is_pdf(f):
    f.seek(0)
    head = f.read(5)
    f.seek(0)
    return head == b"%PDF-"


def validate_image_upload(f, field="image", max_mb=MAX_IMAGE_MB):
    if not f:
        return
    _size_check(f, max_mb, field)
    if not image_format(f):
        raise BusinessRuleError(f"{f.name} is not a valid photo (JPG, PNG or WebP).", field=field)


def validate_document_upload(f, field="file", max_mb=MAX_DOCUMENT_MB):
    """A photo of a bill or a PDF."""
    if not f:
        return
    _size_check(f, max_mb, field)
    if not (image_format(f) or is_pdf(f)):
        raise BusinessRuleError(f"{f.name} must be a photo (JPG, PNG, WebP) or a PDF.", field=field)


def _random_name(filename):
    ext = Path(filename or "").suffix.lower()[:6]
    if ext not in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".pdf"}:
        ext = ""
    return f"{uuid.uuid4().hex}{ext}"


# upload_to callables (module-level so migrations can reference them)
def avatar_path(instance, filename):
    return f"avatars/{_random_name(filename)}"


def logo_path(instance, filename):
    return f"company/{_random_name(filename)}"


def expense_bill_path(instance, filename):
    return f"expenses/{timezone.now():%Y/%m}/{_random_name(filename)}"
