"""Input validation utilities for Brain Guard."""

import re
from typing import Dict, Any


class ValidationError(Exception):
    """Raised when input validation fails."""
    
    def __init__(self, field: str, message: str):
        self.field = field
        self.message = message
        super().__init__(f"Validation error in '{field}': {message}")


def validate_session_id(session_id: str) -> bool:
    """
    Validate session ID format.
    
    Rules:
    - Must be a string
    - 8-64 characters
    - Alphanumeric, hyphens, and underscores only
    
    Args:
        session_id: The session ID to validate
        
    Returns:
        True if valid
        
    Raises:
        ValidationError: If validation fails
    """
    if not isinstance(session_id, str):
        raise ValidationError("session_id", "Must be a string")
    
    if len(session_id) < 8 or len(session_id) > 64:
        raise ValidationError("session_id", "Must be 8-64 characters")
    
    # Allow alphanumeric, hyphens, and underscores
    if not re.match(r'^[a-zA-Z0-9_-]+$', session_id):
        raise ValidationError("session_id", "Must contain only alphanumeric characters, hyphens, and underscores")
    
    return True


def validate_message(message: str) -> bool:
    """
    Validate message content.
    
    Rules:
    - Must be a string
    - 1-10000 characters
    - No null bytes
    
    Args:
        message: The message to validate
        
    Returns:
        True if valid
        
    Raises:
        ValidationError: If validation fails
    """
    if not isinstance(message, str):
        raise ValidationError("message", "Must be a string")
    
    if len(message) < 1:
        raise ValidationError("message", "Cannot be empty")
    
    if len(message) > 10000:
        raise ValidationError("message", "Exceeds maximum length of 10000 characters")
    
    if '\x00' in message:
        raise ValidationError("message", "Contains null bytes which are not allowed")
    
    return True


def validate_context(context: Any) -> bool:
    """
    Validate context dictionary.
    
    Rules:
    - Must be a dictionary if provided
    - All keys must be strings
    - Values should be serializable (str, int, float, bool, None, list, dict)
    
    Args:
        context: The context dictionary to validate
        
    Returns:
        True if valid
        
    Raises:
        ValidationError: If validation fails
    """
    if context is None:
        return True
    
    if not isinstance(context, dict):
        raise ValidationError("context", "Must be a dictionary")
    
    for key, value in context.items():
        if not isinstance(key, str):
            raise ValidationError("context", f"Key '{key}' must be a string")
        
        # Validate value is a simple serializable type
        if not isinstance(value, (str, int, float, bool, type(None), list, dict)):
            raise ValidationError("context", f"Value for key '{key}' has unsupported type")
    
    return True


def sanitize_input(text: str) -> str:
    """
    Sanitize input text by stripping control characters.
    
    Preserves:
    - Newlines (\n)
    - Tabs (\t)
    - Normal printable characters
    
    Removes:
    - Null bytes
    - Other control characters
    
    Args:
        text: The text to sanitize
        
    Returns:
        Sanitized text
    """
    if not isinstance(text, str):
        return ""
    
    # Keep only printable characters plus newlines and tabs
    sanitized = ''.join(
        char for char in text
        if char == '\n' or char == '\t' or (ord(char) >= 32 and ord(char) < 127)
    )
    
    return sanitized


def validate_response(response: str) -> bool:
    """
    Validate response content.
    
    Rules:
    - Must be a string
    - 1-10000 characters
    - No null bytes
    
    Args:
        response: The response to validate
        
    Returns:
        True if valid
        
    Raises:
        ValidationError: If validation fails
    """
    if not isinstance(response, str):
        raise ValidationError("response", "Must be a string")
    
    if len(response) < 1:
        raise ValidationError("response", "Cannot be empty")
    
    if len(response) > 10000:
        raise ValidationError("response", "Exceeds maximum length of 10000 characters")
    
    if '\x00' in response:
        raise ValidationError("response", "Contains null bytes which are not allowed")
    
    return True
