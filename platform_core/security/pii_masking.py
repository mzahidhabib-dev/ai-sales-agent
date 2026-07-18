import re

# Regex for matching standard email addresses
EMAIL_REGEX = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')

# Regex for matching common phone numbers (e.g., 555-123-4567, (555) 123-4567, +1-555-123-4567)
PHONE_REGEX = re.compile(r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}')

def mask_pii(text: str) -> str:
    """
    Detects and masks PII (Emails and Phone Numbers) in a given string.
    
    Args:
        text: The string that may contain PII.
        
    Returns:
        The string with PII replaced by [REDACTED_EMAIL] and [REDACTED_PHONE].
    """
    if not isinstance(text, str):
        return text
        
    # Mask emails
    masked_text = EMAIL_REGEX.sub('[REDACTED_EMAIL]', text)
    
    # Mask phone numbers
    masked_text = PHONE_REGEX.sub('[REDACTED_PHONE]', masked_text)
    
    return masked_text
