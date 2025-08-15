from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class Background(Base):
    __tablename__ = "backgrounds"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    file_path = Column(String, nullable=False)
    category = Column(String, default="custom")  # custom, unsplash, ai_generated
    source_url = Column(String)  # Original Unsplash URL or AI prompt
    created_at = Column(DateTime, default=datetime.utcnow)
    user_id = Column(Integer, ForeignKey("users.id"))

class VideoProcessing(Base):
    __tablename__ = "video_processing"
    
    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(String, nullable=False)  # Your existing video ID
    processing_type = Column(String, nullable=False)  # transparent, green_screen, background_replace
    status = Column(String, default="pending")  # pending, processing, completed, failed
    heygen_job_id = Column(String)
    result_url = Column(String)
    background_id = Column(Integer, ForeignKey("backgrounds.id"))
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    user_id = Column(Integer, ForeignKey("users.id"))
    
    background = relationship("Background")
