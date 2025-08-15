from pydantic import BaseModel, EmailStr, HttpUrl, Field
from typing import Optional, List
from datetime import datetime

class UserBase(BaseModel):
    username: str
    email: EmailStr
    is_admin: Optional[bool] = False

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    username: Optional[str]
    email: Optional[EmailStr]
    password: Optional[str]
    is_admin: Optional[bool]

class UserOut(UserBase):
    id: int
    created_at: datetime
    class Config:
        orm_mode = True

class AvatarBase(BaseModel):
    name: str
    url: HttpUrl

class AvatarCreate(AvatarBase):
    user_id: int

class AvatarUpdate(BaseModel):
    name: Optional[str]
    url: Optional[HttpUrl]
    user_id: Optional[int]

class AvatarOut(AvatarBase):
    id: int
    user_id: int
    created_at: datetime
    class Config:
        orm_mode = True

class VideoBase(BaseModel):
    url: HttpUrl
    status: Optional[str] = "pending"

class VideoCreate(VideoBase):
    user_id: int
    avatar_id: int

class VideoUpdate(BaseModel):
    url: Optional[HttpUrl]
    status: Optional[str]
    user_id: Optional[int]
    avatar_id: Optional[int]

class VideoOut(VideoBase):
    id: int
    user_id: int
    avatar_id: int
    created_at: datetime
    class Config:
        orm_mode = True

class UploadedImageBase(BaseModel):
    filename: str
    url: HttpUrl

class UploadedImageCreate(UploadedImageBase):
    user_id: int

class UploadedImageOut(UploadedImageBase):
    id: int
    user_id: int
    uploaded_at: datetime
    class Config:
        orm_mode = True

class LogEntryOut(BaseModel):
    id: int
    timestamp: datetime
    module: str
    level: str
    message: str
    class Config:
        orm_mode = True
