import io

import piexif
import pytest
from PIL import Image

from app.storage.image_processing import InvalidImageError, process_image


def test_process_image_strips_gps_exif_and_normalizes_to_jpeg():
    # Build a JPEG with a real embedded GPS EXIF tag, the exact leak vector
    # this function exists to close (see process_image's docstring).
    img = Image.new("RGB", (60, 60), color=(0, 128, 255))
    gps_ifd = {
        piexif.GPSIFD.GPSLatitudeRef: "N",
        piexif.GPSIFD.GPSLatitude: ((6, 1), (13, 1), (0, 1)),
        piexif.GPSIFD.GPSLongitudeRef: "W",
        piexif.GPSIFD.GPSLongitude: ((75, 1), (34, 1), (0, 1)),
    }
    exif_bytes = piexif.dump({"GPS": gps_ifd})
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif_bytes)
    raw = buf.getvalue()

    # Sanity check the fixture actually embedded GPS data before processing.
    assert piexif.load(raw)["GPS"]

    clean_bytes, content_type = process_image(raw)

    assert content_type == "image/jpeg"
    reopened = Image.open(io.BytesIO(clean_bytes))
    assert reopened.format == "JPEG"
    assert "exif" not in reopened.info
    assert piexif.load(clean_bytes)["GPS"] == {}


def test_process_image_caps_max_dimension():
    img = Image.new("RGB", (3000, 1500), color=(200, 200, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")

    clean_bytes, _ = process_image(buf.getvalue())

    reopened = Image.open(io.BytesIO(clean_bytes))
    assert max(reopened.size) <= 2000


def test_process_image_rejects_non_image_bytes():
    with pytest.raises(InvalidImageError):
        process_image(b"this is definitely not an image")
