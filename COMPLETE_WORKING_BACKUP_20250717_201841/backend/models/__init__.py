# Import Base first, then models
from backend.db import Base

# Import models (without the star imports to avoid circular issues)
from backend.models.core import User, Avatar, Video, UploadedImage, LogEntry
from backend.models.premium import UserSubscription, PremiumFeature, UserFeatureUsage, UserBackground, BackgroundReplacementJob
