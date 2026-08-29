import re


def validate_password_strength(password: str):
    """
    Returns (is_valid, message).
    Requires: 8+ chars, 1 uppercase, 1 lowercase, 1 digit, 1 special character.
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search(r"[A-Z]", password):
        return False, "Password must include at least one uppercase letter."
    if not re.search(r"[a-z]", password):
        return False, "Password must include at least one lowercase letter."
    if not re.search(r"[0-9]", password):
        return False, "Password must include at least one number."
    if not re.search(r'[!@#$%^&*(),.?":{}|<>_\-+=~`\[\]/;\']', password):
        return False, "Password must include at least one special character (e.g. ! @ # $ %)."
    return True, ""
