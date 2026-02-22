from sqlalchemy import Column, String, DateTime, Float, Integer
from datetime import datetime
from .db import Base


class Image(Base):
    __tablename__ = "images"

    id = Column(String, primary_key=True, index=True)
    original_name = Column(String, nullable=False)
    content_type = Column(String, nullable=False)

    status = Column(String, default="processing")  # processing | success | failed
    error_message = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)
    processing_time_seconds = Column(Float, nullable=True)

    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    format = Column(String, nullable=True)
    size_bytes = Column(Integer, nullable=True)

    caption = Column(String, nullable=True)

    original_path = Column(String, nullable=True)
    thumb_small_path = Column(String, nullable=True)
    thumb_medium_path = Column(String, nullable=True)