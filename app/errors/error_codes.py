# error_codes.py
"""
Central error code taxonomy for MyAvatar and related projects.
"""

class ErrorCodes:
    # Video Processing
    VIDEO_LOAD_FAILED = "E001"
    VIDEO_CORRUPT = "E002"
    VIDEO_TOO_LARGE = "E003"
    VIDEO_PROCESSING_FAILED = "E004"

    # Segmentation
    SEGMENTATION_INIT_FAILED = "E101"
    SEGMENTATION_FRAME_FAILED = "E102"
    SEGMENTATION_CLEANUP_FAILED = "E103"  # WARNING level

    # Output
    OUTPUT_FILE_MISSING = "E201"
    OUTPUT_UPLOAD_FAILED = "E202"
    OUTPUT_SAVE_DB_FAILED = "E203"

    # General
    UNKNOWN_ERROR = "E999"

ERROR_ACTIONS = {
    ErrorCodes.VIDEO_LOAD_FAILED: "Check input video path and format.",
    ErrorCodes.VIDEO_CORRUPT: "Try a different video file.",
    ErrorCodes.VIDEO_TOO_LARGE: "Reduce video size.",
    ErrorCodes.VIDEO_PROCESSING_FAILED: "Check processing logs.",
    ErrorCodes.SEGMENTATION_INIT_FAILED: "Check segmentation model weights.",
    ErrorCodes.SEGMENTATION_FRAME_FAILED: "Check input frames.",
    ErrorCodes.SEGMENTATION_CLEANUP_FAILED: "Review cleanup routine.",
    ErrorCodes.OUTPUT_FILE_MISSING: "Check output path.",
    ErrorCodes.OUTPUT_UPLOAD_FAILED: "Check network/storage.",
    ErrorCodes.OUTPUT_SAVE_DB_FAILED: "Check database connection.",
    ErrorCodes.UNKNOWN_ERROR: "Contact support."
}
