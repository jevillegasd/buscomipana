import io

from PIL import Image, UnidentifiedImageError

ALLOWED_INPUT_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
# Sanity cap applied before cropping, purely to bound how much Pillow decodes
# -- the real output size limit is OUTPUT_SIZE_PX below.
DECODE_GUARD_DIMENSION_PX = 2000
OUTPUT_SIZE_PX = 400
OUTPUT_CONTENT_TYPE = "image/jpeg"


class InvalidImageError(Exception):
    pass


def process_image(raw_bytes: bytes) -> tuple[bytes, str]:
    """Validates the upload is really a decodable image, strips all metadata,
    center-crops to a square, and downsizes to a capped square JPEG.

    Every caller (profile photo, missing-person report photo) is displayed as
    a square/circular thumbnail, so cropping here -- rather than trusting
    every caller to send a pre-cropped square -- guarantees the stored file
    always matches, even for direct API callers that bypass the frontend's
    interactive crop picker.

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
    if max(image.size) > DECODE_GUARD_DIMENSION_PX:
        image.thumbnail((DECODE_GUARD_DIMENSION_PX, DECODE_GUARD_DIMENSION_PX))

    width, height = image.size
    side = min(width, height)
    left = (width - side) // 2
    top = (height - side) // 2
    image = image.crop((left, top, left + side, top + side))

    if side > OUTPUT_SIZE_PX:
        image = image.resize((OUTPUT_SIZE_PX, OUTPUT_SIZE_PX), Image.LANCZOS)

    # Rebuild from raw pixel data into a brand-new Image with no .info dict at
    # all, rather than trusting convert()/crop()/resize() to have dropped
    # every metadata field -- this is the step that actually guarantees no
    # EXIF (and no embedded GPS tag) survives into the stored file.
    clean = Image.frombytes(image.mode, image.size, image.tobytes())

    output = io.BytesIO()
    clean.save(output, format="JPEG", quality=85)
    return output.getvalue(), OUTPUT_CONTENT_TYPE
