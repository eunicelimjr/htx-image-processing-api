import os
import time
import logging
from pathlib import Path
from typing import Tuple, Optional

from PIL import Image as PILImage

logger = logging.getLogger(__name__)

# Lazy-loaded captioner (avoid loading at import time)
_captioner = None


def _get_captioner():
    """
    Best-effort captioner using HuggingFace pipeline.
    Can be disabled by setting DISABLE_CAPTION=1.
    """
    global _captioner

    if os.getenv("DISABLE_CAPTION", "0") == "1":
        return None

    if _captioner is not None:
        return _captioner

    try:
        from transformers import pipeline

        # Smaller than BLIP-large; faster to pull in many environments
        _captioner = pipeline(
            "image-to-text",
            model=os.getenv("CAPTION_MODEL", "nlpconnect/vit-gpt2-image-captioning"),
        )
        logger.info("Caption model loaded.")
        return _captioner
    except Exception as e:
        logger.warning("Failed to load caption model: %s", e)
        _captioner = None
        return None


def _make_thumbnail(img: PILImage.Image, max_side: int) -> PILImage.Image:
    # Copy and resize maintaining aspect ratio, bounded by max_side
    out = img.copy()
    out.thumbnail((max_side, max_side))
    # Ensure JPEG-safe mode
    if out.mode not in ("RGB", "L"):
        out = out.convert("RGB")
    return out


def process_image_file(
    image_id: str,
    original_path: Path,
    thumbs_small_path: Path,
    thumbs_medium_path: Path,
) -> Tuple[dict, dict, Optional[str], float]:
    """
    Returns:
      metadata dict, thumbnails dict, caption str|None, processing_time_seconds float
    Raises:
      Exception on hard failures.
    """
    start = time.perf_counter()

    # Read original with Pillow
    with PILImage.open(original_path) as img:
        width, height = img.size
        fmt = (img.format or "").upper()

        size_bytes = original_path.stat().st_size

        # Thumbnails
        small = _make_thumbnail(img, 128)
        medium = _make_thumbnail(img, 512)

        thumbs_small_path.parent.mkdir(parents=True, exist_ok=True)
        thumbs_medium_path.parent.mkdir(parents=True, exist_ok=True)

        # Save thumbnails as JPEG for consistency
        small.save(thumbs_small_path, format="JPEG", quality=85)
        medium.save(thumbs_medium_path, format="JPEG", quality=85)

    # Caption (best-effort)
    caption = None
    captioner = _get_captioner()
    if captioner is None:
        caption = os.getenv("CAPTION_FALLBACK", "caption_unavailable")
    else:
        try:
            # pipeline expects PIL image or path; using path avoids re-open issues
            out = captioner(str(original_path))
            # Typical output: [{"generated_text": "..."}]
            if isinstance(out, list) and out and "generated_text" in out[0]:
                caption = out[0]["generated_text"]
            else:
                caption = os.getenv("CAPTION_FALLBACK", "caption_unavailable")
        except Exception as e:
            logger.warning("Caption generation failed: %s", e)
            caption = os.getenv("CAPTION_FALLBACK", "caption_unavailable")

    elapsed = time.perf_counter() - start

    metadata = {
        "width": width,
        "height": height,
        "format": fmt if fmt else None,
        "size_bytes": size_bytes,
    }
    thumbnails = {
        "small": f"/api/images/{image_id}/thumbnails/small",
        "medium": f"/api/images/{image_id}/thumbnails/medium",
    }

    return metadata, thumbnails, caption, elapsed