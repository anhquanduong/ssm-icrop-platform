import hashlib
import os
import logging
from typing import Optional, Tuple
from utils.db_manager import DatabaseManager

logger = logging.getLogger(__name__)

def hash_password(password: str, salt: Optional[bytes] = None) -> str:
    """
    Generates a secure PBKDF2 SHA-256 hash using native hashlib with a 16-byte random salt.
    Zero external dependencies required.
    """
    if salt is None:
        salt = os.urandom(16)
    pwd_bytes = password.encode('utf-8')
    # Use PBKDF2 stretching with 100,000 iterations
    key = hashlib.pbkdf2_hmac('sha256', pwd_bytes, salt, 100000)
    # Return formatted as salt_hex$key_hex
    return f"{salt.hex()}${key.hex()}"

def verify_password(stored_hash: str, password: str) -> bool:
    """
    Verifies an incoming password against the secure stored hash string.
    """
    try:
        salt_hex, key_hex = stored_hash.split("$")
        salt = bytes.fromhex(salt_hex)
        stored_key = bytes.fromhex(key_hex)
        pwd_bytes = password.encode('utf-8')
        # Re-derive key
        key = hashlib.pbkdf2_hmac('sha256', pwd_bytes, salt, 100000)
        return key == stored_key
    except Exception as e:
        logger.error(f"Password verification failed due to formatting exception: {e}")
        return False

def register_user(username: str, password: str) -> Tuple[bool, str]:
    """
    Registers a new unique user in the database.
    """
    username_clean = username.strip()
    if len(username_clean) < 3:
        return False, "Username must be at least 3 characters long."
    if len(password) < 6:
        return False, "Password must be at least 6 characters long."
        
    db = DatabaseManager()
    with db.get_connection() as conn:
        cursor = conn.cursor()
        
        # Check if username is already registered
        cursor.execute("SELECT id FROM users WHERE username = ?", (username_clean,))
        if cursor.fetchone() is not None:
            return False, "Username is already registered. Please choose another."
            
        # Hash and save
        pwd_hash = hash_password(password)
        try:
            cursor.execute("""
                INSERT INTO users (username, password_hash)
                VALUES (?, ?)
            """, (username_clean, pwd_hash))
            conn.commit()
            logger.info(f"User '{username_clean}' successfully registered.")
            return True, "User registered successfully!"
        except Exception as e:
            logger.error(f"Error registering user: {e}")
            return False, f"Registration failed: {str(e)}"

def authenticate_user(username: str, password: str) -> Optional[Tuple[int, str]]:
    """
    Authenticates a user against their stored credentials in the SQLite schema.
    Returns (user_id, username) if successful, None otherwise.
    """
    username_clean = username.strip()
    db = DatabaseManager()
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, password_hash FROM users WHERE username = ?", (username_clean,))
        row = cursor.fetchone()
        
        if row is None:
            logger.warning(f"Failed authentication attempt for non-existent user: {username_clean}")
            return None
            
        user_id, pwd_hash = row
        if verify_password(pwd_hash, password):
            logger.info(f"User '{username_clean}' successfully authenticated.")
            return user_id, username_clean
        else:
            logger.warning(f"Failed authentication attempt (incorrect password) for user: {username_clean}")
            return None
