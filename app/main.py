import logging
import os
from pathlib import Path
from uuid import uuid4
from datetime import datetime, timezone

from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .db import engine, get_db
from .models import Base, Image
from .processing import process_image_file

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("htx-api")

app = FastAPI(title="HTX Image Processing API")

# Create database tables
Base.metadata.create_all(bind=engine)

# Storage
STORAGE_DIR = Path(os.getenv("STORAGE_DIR", "storage"))
ORIGINALS_DIR = STORAGE_DIR / "originals"
THUMBS_DIR = STORAGE_DIR / "thumbs"
ORIGINALS_DIR.mkdir(parents=True, exist_ok=True)
(THUMBS_DIR / "small").mkdir(parents=True, exist_ok=True)
(THUMBS_DIR / "medium").mkdir(parents=True, exist_ok=True)


def _dt_to_z(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    # assume stored datetimes are UTC (naive) and emit ISO-8601 with Z
    return dt.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


def _file_mtime_to_z(path_str: str | None) -> str | None:
    if not path_str:
        return None
    try:
        mtime = Path(path_str).stat().st_mtime
        dt = datetime.utcfromtimestamp(mtime)
        return _dt_to_z(dt)
    except Exception:
        return None


def _response_from_row(row: Image, request: Request | None = None, include_caption: bool = True):
    # metadata
    metadata = {}
    if row.width is not None:
        metadata = {
            "width": row.width,
            "height": row.height,
            "format": (row.format.lower() if row.format else None),
            "size_bytes": row.size_bytes,
        }
        file_dt = _file_mtime_to_z(row.original_path)
        if file_dt:
            metadata["file_datetime"] = file_dt

    # thumbnails
    thumbnails = {}
    if row.thumb_small_path and row.thumb_medium_path:
        small_rel = f"/api/images/{row.id}/thumbnails/small"
        medium_rel = f"/api/images/{row.id}/thumbnails/medium"

        if request is not None:
            base = str(request.base_url).rstrip("/")
            thumbnails = {
                "small": base + small_rel,
                "medium": base + medium_rel,
            }
        else:
            thumbnails = {
                "small": small_rel,
                "medium": medium_rel,
            }

    data = {
        "image_id": row.id,
        "original_name": row.original_name,
        "processed_at": _dt_to_z(row.processed_at),
        "metadata": metadata,
        "thumbnails": thumbnails,
        "caption" :row.caption,
    }

    if include_caption:
        data["caption"] = row.caption

    return {
        "status": row.status,
        "data": data,
        "error": row.error_message,
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/images")
def upload_image(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    # Invalid format should return spec-shaped JSON (not FastAPI "detail")
    if file.content_type not in ("image/jpeg", "image/png"):
        image_id = str(uuid4())
        row = Image(
            id=image_id,
            original_name=file.filename,
            content_type=file.content_type or "application/octet-stream",
            status="failed",
            created_at=datetime.utcnow(),
            processed_at=datetime.utcnow(),
            error_message="invalid file format",
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        # No Request object here; relative URLs are fine for upload response
        return _response_from_row(row, request=None, include_caption=True)

    image_id = str(uuid4())
    ext = ".jpg" if file.content_type == "image/jpeg" else ".png"

    original_path = ORIGINALS_DIR / f"{image_id}{ext}"
    small_thumb_path = THUMBS_DIR / "small" / f"{image_id}.jpg"
    medium_thumb_path = THUMBS_DIR / "medium" / f"{image_id}.jpg"

    # Save original
    content = file.file.read()
    file.file.close()
    with open(original_path, "wb") as f:
        f.write(content)

    # Create DB row (processing)
    row = Image(
        id=image_id,
        original_name=file.filename,
        content_type=file.content_type,
        status="processing",
        created_at=datetime.utcnow(),
        original_path=str(original_path),
    )
    db.add(row)
    db.commit()

    # Process synchronously
    try:
        metadata, _thumbs, caption, elapsed = process_image_file(
            image_id=image_id,
            original_path=original_path,
            thumbs_small_path=small_thumb_path,
            thumbs_medium_path=medium_thumb_path,
        )

        row.status = "success"
        row.processed_at = datetime.utcnow()
        row.processing_time_seconds = float(elapsed)

        row.width = metadata.get("width")
        row.height = metadata.get("height")
        row.format = metadata.get("format")
        row.size_bytes = metadata.get("size_bytes")

        row.thumb_small_path = str(small_thumb_path)
        row.thumb_medium_path = str(medium_thumb_path)

        row.caption = caption
        row.error_message = None

        db.add(row)
        db.commit()
        db.refresh(row)

        return _response_from_row(row, request=None, include_caption=True)

    except Exception as e:
        logger.exception("Processing failed for %s", image_id)
        row.status = "failed"
        row.processed_at = datetime.utcnow()
        row.error_message = str(e)
        db.add(row)
        db.commit()
        db.refresh(row)
        return _response_from_row(row, request=None, include_caption=True)


@app.get("/api/images")
def list_images(request: Request, db: Session = Depends(get_db)):
    rows = db.query(Image).order_by(Image.created_at.desc()).all()
    # Spec sample doesn't show caption for list; keep include_caption=False for closer match
    return [_response_from_row(r, request=request, include_caption=False) for r in rows]


@app.get("/api/images/{image_id}")
def get_image(image_id: str, request: Request, db: Session = Depends(get_db)):
    row = db.query(Image).filter(Image.id == image_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Image not found")
    # Show analysis (caption) here
    return _response_from_row(row, request=request, include_caption=True)


@app.get("/api/images/{image_id}/thumbnails/{size}")
def get_thumbnail(image_id: str, size: str, db: Session = Depends(get_db)):
    if size not in ("small", "medium"):
        raise HTTPException(status_code=400, detail="size must be small or medium")

    row = db.query(Image).filter(Image.id == image_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Image not found")

    path = row.thumb_small_path if size == "small" else row.thumb_medium_path
    if not path:
        raise HTTPException(status_code=404, detail="Thumbnail not found")

    p = Path(path)
    if not p.exists():
        raise HTTPException(status_code=404, detail="Thumbnail file missing")

    return FileResponse(p, media_type="image/jpeg")


@app.get("/api/stats")
def stats(db: Session = Depends(get_db)):
    rows = db.query(Image).all()
    total_images = len(rows)
    failed_images = len([r for r in rows if r.status == "failed"])
    successful_images = len([r for r in rows if r.status == "success"])

    success_times = [
        r.processing_time_seconds
        for r in rows
        if r.status == "success" and r.processing_time_seconds is not None
    ]
    average_processing_time_seconds = (
        sum(success_times) / len(success_times) if success_times else 0.0
    )

    success_rate_percent = (
        (successful_images / total_images) * 100.0 if total_images else 0.0
    )

    # Keep your existing keys (tests), but values are aligned to spec intent
    return {
        "total_images": total_images,
        "successful_images": successful_images,
        "failed_images": failed_images,
        "success_rate_percent": round(success_rate_percent, 2),
        "average_processing_time_seconds": round(average_processing_time_seconds, 4),
    }