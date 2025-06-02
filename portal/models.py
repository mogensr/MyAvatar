# portal/models.py
from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, DateTime
from sqlalchemy.orm import relationship
import datetime

from .database import Base

class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    logo_url = Column(String)
    subdomain = Column(String, unique=True)

    # Relationer
    users = relationship("User", back_populates="organization")
    avatars = relationship("Avatar", back_populates="organization")

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    linkedin_id = Column(String, unique=True, index=True, nullable=True)
    email = Column(String, unique=True, index=True)
    name = Column(String)
    profile_picture = Column(String)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    password_hash = Column(String, nullable=True)  # Tilføjet for email+password login

    # Relationer
    organization = relationship("Organization", back_populates="users")
    videos = relationship("Video", back_populates="user")

class Avatar(Base):
    __tablename__ = "avatars"

    id = Column(Integer, primary_key=True, index=True)
    heygen_avatar_id = Column(String, nullable=False)
    name = Column(String, nullable=False)
    type = Column(String)
    thumbnail_url = Column(String)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)

    # Relationer
    organization = relationship("Organization", back_populates="avatars")
    videos = relationship("Video", back_populates="avatar")

class Video(Base):
    __tablename__ = "videos"

    id = Column(Integer, primary_key=True, index=True)
    heygen_video_id = Column(String, nullable=False)
    title = Column(String)
    video_url = Column(String)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    avatar_id = Column(Integer, ForeignKey("avatars.id"), nullable=False)

    # Relationer
    user = relationship("User", back_populates="videos")
    avatar = relationship("Avatar", back_populates="videos")
