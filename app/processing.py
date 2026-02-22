import os
import time
import logging
from pathlib import Path
from typing import Tuple, Optional

from PIL import Image as PILImage

logger = logging.getLogger(__name__)

# Lazy-loaded caption model/processor
_blip_processor = None
_blip_model = None
_blip_device = None


def _get_blip():
    """
    Best-effort captioning using HuggingFace BLIP.
    Disable by setting DISABLE_CAPTION=1.
    Override model via CAPTION_MODEL env var.
    """
    global _blip_processor, _blip_model, _blip_device

    if os.getenv("DISABLE_CAPTION", "0") == "1":
        return None, None, None

    if _blip_processor is not None and _blip_model is not None:
        return _blip_processor, _blip_model, _blip_device

    try:
        import torch
        from transformers import BlipProcessor, BlipForConditionalGeneration

        model_name = os.getenv("CAPTION_MODEL", "Salesforce/blip-image-captioning-large")

        # Pick device
        device = "cuda" if torch.cuda.is_available() else "cpu"

        processor = BlipProcessor.from_pretrained(model_name)
        model = BlipForConditionalGeneration.from_pretrained(model_name)

        model.to(device)
        model.eval()

        _blip_processor = processor
        _blip_model = model
        _blip_device = device

        logger.info("BLIP caption model loaded: %s (device=%s)", model_name, device)
        return _blip_processor, _blip_model, _blip_device

    except Exception:
        logger.exception("Failed to load BLIP caption model")
        _blip_processor, _blip_model, _blip_device = None, None, None
        return None, None, None


def _make_thumbnail(img: PILImage.Image, max_side: int) -> PILImage.Image:
    """
    Resize maintaining aspect ratio, bounded by max_side.
    Output is forced to RGB/L so it can be saved as JPEG.
    """
    out = img.copy()
    out.thumbnail((max_side, max_side))
    if out.mode not in ("RGB", "L"):
        out = out.convert("RGB")
    return out


def _file_mtime_iso_z(path: Path) -> str:
    """
    Return file modified time as ISO-8601 with Z (UTC).
    """
    import datetime
    ts = path.stat().st_mtime
    return (
        datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


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

    size_bytes = original_path.stat().st_size
    file_datetime_iso = _file_mtime_iso_z(original_path)

    # Open image
    with PILImage.open(original_path) as img:
        width, height = img.size
        fmt = (img.format or "").upper()

        # Thumbnails
        small = _make_thumbnail(img, 128)
        medium = _make_thumbnail(img, 512)

        thumbs_small_path.parent.mkdir(parents=True, exist_ok=True)
        thumbs_medium_path.parent.mkdir(parents=True, exist_ok=True)

        small.save(thumbs_small_path, format="JPEG", quality=85)
        medium.save(thumbs_medium_path, format="JPEG", quality=85)

        # Captioning (best-effort)
        processor, model, device = _get_blip()
        if processor is None or model is None:
            caption = os.getenv("CAPTION_FALLBACK", "caption_unavailable")
        else:
            try:
                import torch

                # BLIP expects RGB images
                cap_img = img.convert("RGB")

                inputs = processor(images=cap_img, return_tensors="pt")
                inputs = {k: v.to(device) for k, v in inputs.items()}

                with torch.no_grad():
                    output_ids = model.generate(
                        **inputs,
                        max_new_tokens=30,
                    )

                caption = processor.decode(output_ids[0], skip_special_tokens=True).strip()
                if not caption:
                    caption = os.getenv("CAPTION_FALLBACK", "caption_unavailable")

            except Exception:
                logger.exception("Caption generation failed")
                caption = os.getenv("CAPTION_FALLBACK", "caption_unavailable")

    elapsed = time.perf_counter() - start

    metadata = {
        "width": width,
        "height": height,
        "format": fmt.lower() if fmt else None,
        "size_bytes": size_bytes,
        "file_datetime": file_datetime_iso,
    }

    thumbnails = {
        "small": f"/api/images/{image_id}/thumbnails/small",
        "medium": f"/api/images/{image_id}/thumbnails/medium",
    }

    return metadata, thumbnails, caption, elapsed