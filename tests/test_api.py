import os
import tempfile
from pathlib import Path

from PIL import Image as PILImage
from fastapi.testclient import TestClient


def _make_png_bytes():
    img = PILImage.new("RGB", (64, 32), color=(255, 0, 0))
    import io

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()


def test_endpoints_basic():
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        os.environ["DATABASE_URL"] = f"sqlite:///{td_path / 'test.db'}"
        os.environ["STORAGE_DIR"] = str(td_path / "storage")
        os.environ["DISABLE_CAPTION"] = "1"  # avoid downloading model during tests
        os.environ["CAPTION_FALLBACK"] = "caption_unavailable"

        # Import AFTER env vars set
        from app.main import app  # noqa
        from app.db import engine  # <-- import engine AFTER env vars too

        client = TestClient(app)

        # health
        r = client.get("/health")
        assert r.status_code == 200

        # upload
        png_bytes = _make_png_bytes()
        r = client.post(
            "/api/images",
            files={"file": ("test.png", png_bytes, "image/png")},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["status"] in ("success", "failed")
        assert body["data"]["image_id"]
        image_id = body["data"]["image_id"]

        # list
        r = client.get("/api/images")
        assert r.status_code == 200
        assert isinstance(r.json(), list)
        assert len(r.json()) >= 1

        # get by id
        r = client.get(f"/api/images/{image_id}")
        assert r.status_code == 200
        assert r.json()["data"]["image_id"] == image_id

        # thumbnail (only if success)
        if body["status"] == "success":
            r = client.get(f"/api/images/{image_id}/thumbnails/small")
            assert r.status_code == 200
            assert r.headers["content-type"].startswith("image/")

        # stats
        r = client.get("/api/stats")
        assert r.status_code == 200
        stats = r.json()
        assert "total_images" in stats

        # IMPORTANT (Windows): close DB connections so temp folder can delete test.db
        engine.dispose()