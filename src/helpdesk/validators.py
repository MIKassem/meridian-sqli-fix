# validators.py — validators for file uploads
import logging
import os

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

from helpdesk import settings as helpdesk_settings

logger = logging.getLogger("helpdesk.uploads")

MAX_UPLOAD_BYTES = 5 * 1024 * 1024   # 5 MB, below nginx's 10m so both layers are visible
MAX_IMAGE_PIXELS = 20_000_000
IMAGE_FORMATS = {".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG"}

def _reject(check, ext, size, message):
    # log the decision, never the file contents or the raw filename
    logger.warning("upload_rejected check=%s ext=%r size=%s", check, ext[:16], size)
    raise ValidationError(message)


def validate_file_extension(value):
    name = os.path.basename(value.name)
    ext = os.path.splitext(name)[1].lower()
    size = getattr(value, "size", None)

    if name.count(".") > 1:
        _reject("double_extension", ext, size,
                _("Filenames with more than one extension are not allowed."))

    if size is None or size > MAX_UPLOAD_BYTES:          # fail closed if size unknown
        _reject("too_large", ext, size, _("File is too large (max 5 MB)."))

    if not helpdesk_settings.HELPDESK_VALIDATE_ATTACHMENT_TYPES:
        return

    if ext not in helpdesk_settings.HELPDESK_VALID_EXTENSIONS:
        _reject("extension", ext, size, _("Unsupported file extension: ") + ext)
    
    if ext in IMAGE_FORMATS:
        _validate_image(value, ext, size)
        
    logger.info("upload_accepted ext=%r size=%s", ext, size)
    
    
def _validate_image(value, ext, size):
    from PIL import Image
    try:
        value.seek(0)
        with Image.open(value) as img:
            w, h = img.size
            if w * h > MAX_IMAGE_PIXELS:
                _reject("pixel_bomb", ext, size, _("Image dimensions are too large."))
            if img.format != IMAGE_FORMATS[ext]:
                _reject("type_mismatch", ext, size, _("File content does not match its extension."))
            img.verify()
    except ValidationError:
        raise
    except Image.DecompressionBombError:             
        _reject("pixel_bomb", ext, size, _("Image dimensions are too large."))
    except Exception:
        _reject("not_an_image", ext, size, _("File is not a valid image."))
    finally:
        value.seek(0)
