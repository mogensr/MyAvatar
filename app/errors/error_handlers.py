# error_handlers.py
"""
Error handling and validation helpers for MyAvatar and related projects.
"""
from datetime import datetime
from .error_codes import ERROR_ACTIONS


def create_processing_error(code: str, message: str, level: str = "critical", context: dict = None) -> dict:
    return {
        "error_code": code,
        "message": message,
        "level": level,
        "context": context or {},
        "timestamp": datetime.now().isoformat(),
        "suggested_action": ERROR_ACTIONS.get(code, "Contact support")
    }


def validate_processing_success(output_path: str, expected_size_range: tuple = None) -> tuple:
    """
    Validate processing actually succeeded
    Returns: (is_valid: bool, error_details: dict)
    """
    import os
    if not os.path.exists(output_path):
        return False, create_processing_error("E201", "Output file not created")

    file_size = os.path.getsize(output_path)
    if file_size == 0:
        return False, create_processing_error("E201", "Output file is empty")

    if expected_size_range and not (expected_size_range[0] <= file_size <= expected_size_range[1]):
        return False, create_processing_error("E202", f"Output file size suspicious: {file_size} bytes")

    return True, None
