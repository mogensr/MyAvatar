# exceptions.py
"""
Custom exception classes for structured error handling in MyAvatar and related projects.
"""

class ProcessingException(Exception):
    def __init__(self, error_code, message, context=None):
        self.error_code = error_code
        self.context = context or {}
        super().__init__(message)

    def __str__(self):
        base = super().__str__()
        return f"[{self.error_code}] {base} | Context: {self.context}"
