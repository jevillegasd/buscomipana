import io

from PIL import Image, UnidentifiedImageError

ALLOWED_INPUT_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_DIMENSION_PX = 2000
OUTPUT_CONTENT_TYPE = "image/jpeg"


class InvalidImageError(Exception):
    pass


def process_image(raw_bytes: bytes) -> tuple[bytes, str]:
    """Validates the upload is really a decodable image, strips all metadata,
    and normalizes to a capped-size JPEG.

    Stripping metadata matters specifically for this app: JPEG/EXIF commonly
    embeds GPS coordinates from the phone that took the photo, which would
    leak location data completely outside the handshake/responder gating the
    rest of the app enforces (visibility_service.can_view_location). Pillow's
    built-in DecompressionBomb guard also caps pixel count, so this doubles as
    basic protection against oversized/malicious image files."""
    try:
        probe = Image.open(io.BytesIO(raw_bytes))
        probe.verify()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        # DecompressionBombError is Pillow's own guard against a small file that
        # decodes into a huge pixel buffer (a classic image-upload DoS) -- it
        # isn't an OSError subclass, so it has to be caught explicitly or it
        # propagates as an unhandled 500 instead of a clean rejection.
        raise InvalidImageError("File is not a valid image") from exc

    # verify() leaves the file object unusable for further decoding -- reopen.
    image = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
    if max(image.size) > MAX_DIMENSION_PX:
        image.thumbnail((MAX_DIMENSION_PX, MAX_DIMENSION_PX))

    # Rebuild from raw pixel data into a brand-new Image with no .info dict at
    # all, rather than trusting convert()/thumbnail() to have dropped every
    # metadata field -- this is the step that actually guarantees no EXIF
    # (and no embedded GPS tag) survives into the stored file.
    clean = Image.frombytes(image.mode, image.size, image.tobytes())

    output = io.BytesIO()
    clean.save(output, format="JPEG", quality=85)
    return output.getvalue(), OUTPUT_CONTENT_TYPE
