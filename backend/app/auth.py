from dataclasses import dataclass
from typing import Any, Callable, FrozenSet
import uuid

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.app.config import settings

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: uuid.UUID
    clearances: FrozenSet[str]
    claims: dict[str, Any]


def _decode_bearer_token(token: str) -> AuthenticatedUser:
    if not settings.JWT_SECRET_KEY or not settings.JWT_ISSUER or not settings.JWT_AUDIENCE:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="JWT verifier is not configured")
    try:
        claims = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            audience=settings.JWT_AUDIENCE,
            issuer=settings.JWT_ISSUER,
            options={"require": ["exp", "iat", "sub", "clearances"]},
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    try:
        user_id = uuid.UUID(str(claims["sub"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="JWT subject must be a UUID") from exc

    raw_clearances = claims.get("clearances")
    if not isinstance(raw_clearances, list) or not raw_clearances or not all(
        isinstance(clearance, str) and clearance.strip() for clearance in raw_clearances
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="JWT lacks usable authorization clearances")

    return AuthenticatedUser(user_id=user_id, clearances=frozenset(raw_clearances), claims=claims)


async def get_current_authenticated_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> AuthenticatedUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer authentication is required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _decode_bearer_token(credentials.credentials)


async def get_secondary_authenticated_user(request: Request) -> AuthenticatedUser:
    """Verify a separately issued dual-control JWT; never accept a user UUID input."""
    value = request.headers.get("X-Dual-Control-Authorization", "")
    scheme, _, token = value.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Second bearer authorization is required")
    return _decode_bearer_token(token)


def require_clearance(clearance: str) -> Callable[[AuthenticatedUser], AuthenticatedUser]:
    async def dependency(user: AuthenticatedUser = Depends(get_current_authenticated_user)) -> AuthenticatedUser:
        if clearance not in user.clearances:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Required JWT clearance missing: {clearance}")
        return user

    return dependency
