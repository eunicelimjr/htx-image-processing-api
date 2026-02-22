# HTX Image Processing API

A FastAPI-based image processing service that supports image uploads, thumbnail generation, metadata extraction, AI captioning (BLIP), and processing statistics.

Built as part of a technical assessment.

---

## 🚀 Features

### POST `/api/images`
- Accept JPG and PNG image uploads
- Generate two thumbnails (small & medium)
- Extract metadata:
  - width
  - height
  - format
  - file size (bytes)
  - file datetime (UTC)
- Generate AI caption using:
  - `Salesforce/blip-image-captioning-large`
- Store results in SQLite database
- Return structured JSON response

### GET `/api/images`
- List all processed images
- Includes:
  - processing status
  - metadata
  - thumbnails
  - caption

### GET `/api/images/{id}`
- Retrieve specific image details
- Includes thumbnails and caption

### GET `/api/images/{id}/thumbnails/{small|medium}`
- Return generated thumbnail image

### GET `/api/stats`
- Processing statistics:
  - total images
  - success / failure count
  - success rate
  - average processing time

---

## 🧠 AI Captioning

Uses HuggingFace BLIP model:

Salesforce/blip-image-captioning-large

Captioning behavior:
- Lazy-loaded (model loads only when needed)
- Automatically falls back if disabled or fails

Environment variables:

DISABLE_CAPTION=1              # Disable AI captioning  
CAPTION_MODEL=<model_name>     # Override caption model  
CAPTION_FALLBACK=...           # Custom fallback caption text  

---

## 🗄️ Database

Uses SQLite.

Database file:
htx_images.db

Persisted fields:
- image id
- original filename
- content type
- processing status
- timestamps
- metadata
- thumbnail paths
- caption
- processing time

---

## 📦 Installation

### 1. Clone the repository

git clone <your-repo-url>  
cd htx-image-processing-api  

### 2. Create virtual environment

python -m venv .venv  
.\.venv\Scripts\activate  

### 3. Install dependencies

pip install -r requirements.txt  

---

## ▶️ Running the API

uvicorn app.main:app --reload  

Open in browser:

http://127.0.0.1:8000/docs

Swagger UI is enabled for testing.

---

## 🧪 Running Tests

python -m pytest -q  

Tests cover:
- health endpoint
- upload
- listing
- get by id
- thumbnail retrieval
- stats endpoint

---

## 📁 Project Structure

app/  
 ├── main.py          # FastAPI routes  
 ├── processing.py    # Image processing + AI captioning  
 ├── models.py        # SQLAlchemy models  
 ├── db.py            # Database configuration  

storage/  
 ├── originals/  
 └── thumbs/  
     ├── small/  
     └── medium/  

tests/  
 └── test_api.py  

---

## ⚙️ Design Decisions

- SQLite chosen for simplicity and portability
- Synchronous processing for clarity and reliability
- Lazy model loading to reduce startup cost
- Defensive error handling to ensure consistent API response format
- ISO-8601 timestamps (UTC)

---

## 📌 Supported Formats

- JPG
- PNG

Invalid formats return structured failure responses.

---

## 📊 Example Response

{
  "status": "success",
  "data": {
    "image_id": "1234",
    "original_name": "photo.png",
    "processed_at": "2026-02-22T17:42:40Z",
    "metadata": {
      "width": 448,
      "height": 448,
      "format": "png",
      "size_bytes": 81203,
      "file_datetime": "2026-02-22T17:42:37Z"
    },
    "thumbnails": {
      "small": "/api/images/1234/thumbnails/small",
      "medium": "/api/images/1234/thumbnails/medium"
    },
    "caption": "there are two keys that are sitting side by side"
  },
  "error": null
}

---

## 🏁 Status

All required endpoints implemented.  
AI captioning working.  
Processing statistics implemented.  
Database persistence enabled.