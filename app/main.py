from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException, Depends
from sqlalchemy.orm import Session
from uuid import uuid4
from pathlib import Path
from datetime import datetime

from .db import engine, get_db
from .models import Base, Image

app = FastAPI(title="HTX Image Processing API")

# Create database tables
Base.metadata.create_all(bind=engine)

# Storage paths
STORAGE_DIR = Path("storage")
ORIGINALS_DIR = STORAGE_DIR / "originals"
ORIGINALS_DIR.mkdir(parents=True, exist_ok=True)

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/images")
def upload_image(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    # Basic validation (we'll harden this later)
    if file.content_type not in ("image/jpeg", "image/png"):
        raise HTTPException(status_code=400, detail="Only JPG and PNG files are allowed")

    image_id = str(uuid4())
    ext = ".jpg" if file.content_type == "image/jpeg" else ".png"
    save_path = ORIGINALS_DIR / f"{image_id}{ext}"

    # Save file to disk
    content = file.file.read()
    with open(save_path, "wb") as f:
        f.write(content)

    # Create DB row with status = processing
    row = Image(
        id=image_id,
        original_name=file.filename,
        content_type=file.content_type,
        status="processing",
        created_at=datetime.utcnow(),
        original_path=str(save_path),
    )
    db.add(row)
    db.commit()

    # (Bonus) We'll add background processing later
    # background_tasks.add_task(process_image, image_id)

    return {
        "status": "processing",
        "data": {
            "image_id": image_id,
            "original_name": file.filename,
            "processed_at": None,
            "metadata": {},
            "thumbnails": {},
        },
        "error": None,
    }

@app.get("/api/images")
def list_images(db: Session = Depends(get_db)):
    rows = db.query(Image).all()

    response = []

    for row in rows:
        response.append({
            "status": row.status,
            "data": {
                "image_id": row.id,
                "original_name": row.original_name,
                "processed_at": row.processed_at,
                "metadata": {},
                "thumbnails": {},
            },
            "error": row.error_message,
        })

    return response