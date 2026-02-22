import logging
from pathlib import Path
from uuid import uuid4
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
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
STORAGE_DIR = Path(__import__("os").getenv("STORAGE_DIR", "storage"))
ORIGINALS_DIR = STORAGE_DIR / "originals"
THUMBS_DIR = STORAGE_DIR / "thumbs"
ORIGINALS_DIR.mkdir(parents=True, exist_ok=True)
(THUMBS_DIR / "small").mkdir(parents=True, exist_ok=True)
(THUMBS_DIR / "medium").mkdir(parents=True, exist_ok=True)


def _response_from_row(row: Image):
    metadata = {
        "width": row.width,
        "height": row.height,
        "format": row.format,
        "size_bytes": row.size_bytes,
    } if row.width is not None else {}

    thumbnails = {}
    if row.thumb_small_path and row.thumb_medium_path:
        thumbnails = {
            "small": f"/api/images/{row.id}/thumbnails/small",
            "medium": f"/api/images/{row.id}/thumbnails/medium",
        }

    return {
        "status": row.status,
        "data": {
            "image_id": row.id,
            "original_name": row.original_name,
            "processed_at": row.processed_at,
            "metadata": metadata,
            "thumbnails": thumbnails,
            "caption": row.caption,
        },
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
    if file.content_type not in ("image/jpeg", "image/png"):
        raise HTTPException(status_code=400, detail="Only JPG and PNG files are allowed")

    image_id = str(uuid4())
    ext = ".jpg" if file.content_type == "image/jpeg" else ".png"

    original_path = ORIGINALS_DIR / f"{image_id}{ext}"
    small_thumb_path = THUMBS_DIR / "small" / f"{image_id}.jpg"
    medium_thumb_path = THUMBS_DIR / "medium" / f"{image_id}.jpg"

    # Save original
    content = file.file.read()
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

    # Process synchronously (fastest path for <1 day)
    try:
        metadata, thumbnails, caption, elapsed = process_image_file(
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

        return _response_from_row(row)

    except Exception as e:
        logger.exception("Processing failed for %s", image_id)
        row.status = "failed"
        row.processed_at = datetime.utcnow()
        row.error_message = str(e)
        db.add(row)
        db.commit()
        db.refresh(row)
        return _response_from_row(row)


@app.get("/api/images")
def list_images(db: Session = Depends(get_db)):
    rows = db.query(Image).order_by(Image.created_at.desc()).all()
    return [_response_from_row(r) for r in rows]


@app.get("/api/images/{image_id}")
def get_image(image_id: str, db: Session = Depends(get_db)):
    row = db.query(Image).filter(Image.id == image_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Image not found")
    return _response_from_row(row)


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
    total = len(rows)
    failed = len([r for r in rows if r.status == "failed"])
    success = len([r for r in rows if r.status == "success"])

    success_times = [
        r.processing_time_seconds
        for r in rows
        if r.status == "success" and r.processing_time_seconds is not None
    ]

    avg_time = (sum(success_times) / len(success_times)) if success_times else 0.0

    success_rate = (success / total * 100.0) if total > 0 else 0.0

    return {
        "total": total,
        "failed": failed,
        "success_rate": f"{round(success_rate, 2)}%",
        "average_processing_time_seconds": round(avg_time, 2),
    }