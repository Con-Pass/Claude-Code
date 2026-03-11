import os

import jwt
from datetime import datetime, timedelta
from typing import Optional
from pydantic import BaseModel
from dotenv import load_dotenv
load_dotenv()

def generate_jwt_token(
        action: BaseModel,
        secret_key: str = os.getenv("CONPASS_JWT_SECRET"),
        algorithm: str = "HS256",
        expiration_minutes: Optional[int] = 10
) -> str:
    """
    Generate a JWT token from a Pydantic model (like UpdateMetadataAction).

    Args:
        action: Pydantic model instance to encode
        secret_key: Secret key for JWT signing
        algorithm: JWT algorithm (default: HS256)
        expiration_minutes: Token expiration time in minutes (None for no expiration)

    Returns:
        JWT token string
    """
    # Convert Pydantic model to dict (mode='json' ensures JSON serializable output)
    payload = action.model_dump(mode='json')

    # Add standard JWT claims (as timestamps)
    current_time = datetime.now()
    payload["iat"] = int(current_time.timestamp())

    if expiration_minutes:
        exp_time = current_time + timedelta(minutes=expiration_minutes)
        payload["exp"] = int(exp_time.timestamp())

    # Generate JWT token
    token = jwt.encode(payload, secret_key, algorithm=algorithm)

    return token


def decode_jwt_token(
        token: str,
        secret_key: str = os.getenv("CONPASS_JWT_SECRET"),
        algorithm: str = "HS256"
) -> dict:
    """
    Decode and verify a JWT token.

    Args:
        token: JWT token string
        secret_key: Secret key for JWT verification
        algorithm: JWT algorithm (default: HS256)

    Returns:
        Decoded payload as dictionary

    Raises:
        jwt.ExpiredSignatureError: If token is expired
        jwt.InvalidTokenError: If token is invalid
    """
    payload = jwt.decode(token, secret_key, algorithms=[algorithm])
    return payload