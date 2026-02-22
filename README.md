# HTX Image Processing Pipeline API

## Overview

This project implements a RESTful Image Processing Pipeline API as required by the HTX Software Engineering Technical Assessment.

The API performs the following:

- Accepts image uploads (JPG, PNG)
- Extracts image metadata (width, height, format, file size)
- Generates two thumbnails (small and medium)
- Generates an AI caption using a HuggingFace model
- Stores results in a SQLite database
- Provides image retrieval endpoints
- Provides processing statistics

All responses follow the structured format required in the assessment document.

---

## Architecture Overview

### Processing Pipeline

1. Image is uploaded via `POST /api/images`
2. Image is saved locally under `storage/originals/`
3. Metadata is extracted using Pillow:
   - Width
   - Height
   - Format
   - File size in bytes
4. Two thumbnails are generated:
   - Small (max 128px dimension)
   - Medium (max 512px dimension)
5. AI caption is generated using a HuggingFace Transformer model
6. All results are stored in a SQLite database
7. A structured JSON response is returned

---

## Technology Stack

- FastAPI
- SQLAlchemy
- SQLite
- Pillow
- HuggingFace Transformers
- PyTorch
- Uvicorn
- PyTest

---

## Project Structure

```
htx-image-processing-api/
│
├── app/
│   ├── main.py
│   ├── db.py
│   ├── models.py
│   └── processing.py
│
├── tests/
│   └── test_api.py
│
├── storage/                # Ignored in git
├── requirements.txt
├── README.md
└── htx_images.db           # Ignored in git
```

---

## Setup Instructions

### 1. Clone the Repository

```
git clone <your-repository-url>
cd htx-image-processing-api
```

---

### 2. Create Virtual Environment

#### Windows

```
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

#### Mac / Linux

```
python3 -m venv .venv
source .venv/bin/activate
```

---

### 3. Install Dependencies

```
pip install -r requirements.txt
```

All dependencies are version-pinned for reproducibility.

---

### 4. Run the Application

```
uvicorn app.main:app --reload
```

API Base URL:

```
http://127.0.0.1:8000
```

Swagger Documentation:

```
http://127.0.0.1:8000/docs
```

---

## API Endpoints

### POST `/api/images`

Uploads an image and processes it.

Supported formats:
- JPG
- PNG

Example response:

```json
{
  "status": "success",
  "data": {
    "image_id": "uuid",
    "original_name": "photo.png",
    "processed_at": "2026-02-22T12:00:00Z",
    "metadata": {
      "width": 1396,
      "height": 550,
      "format": "PNG",
      "size_bytes": 43931,
      "caption": "Generated caption"
    },
    "thumbnails": {
      "small": "/api/images/{id}/thumbnails/small",
      "medium": "/api/images/{id}/thumbnails/medium"
    }
  },
  "error": null
}
```

---

### GET `/api/images`

Returns a list of processed images.

---

### GET `/api/images/{id}`

Returns detailed information about a specific image.

---

### GET `/api/images/{id}/thumbnails/{small|medium}`

Returns the requested thumbnail image file.

---

### GET `/api/stats`

Returns processing statistics.

Example:

```json
{
  "total": 3,
  "failed": 0,
  "success_rate": "100.0%",
  "average_processing_time_seconds": 0.52
}
```

---

## Running Tests

To run unit tests:

```
pytest
```

Tests cover:

- Health endpoint
- Image upload
- Image retrieval
- Statistics endpoint

---

## Error Handling

The API includes handling for:

- Unsupported file formats
- Corrupted image files
- Missing image IDs
- Missing thumbnails
- Processing failures

All error responses follow the required structured format:

```
{
  "status": "failed",
  "data": null,
  "error": "error message"
}
```

---

## Logging

Application logging is implemented using Python’s built-in `logging` module instead of print statements.

---

## Notes

- SQLite database file: `htx_images.db`
- Uploaded files stored under `storage/`
- The `storage/` directory and database file are ignored in git
- Dependencies are pinned in `requirements.txt`
- Swagger UI is available at `/docs`

---

## Compliance

This implementation satisfies all mandatory requirements of the HTX Software Engineering Assessment:

- Image upload
- Thumbnail generation
- Metadata extraction
- AI captioning
- Statistics endpoint
- Structured response format
- Logging
- Error handling
- Unit testing