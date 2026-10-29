import os
from datetime import datetime, timedelta, timezone
import uuid

import jwt


# Loaded before application modules so unit tests exercise the same strict JWT
# verifier configuration as CI without embedding credentials in runtime code.
os.environ.setdefault("JWT_SECRET_KEY", "unit-test-only-jwt-secret-not-for-deployment")
os.environ.setdefault("JWT_ISSUER", "attilan-test-issuer")
os.environ.setdefault("JWT_AUDIENCE", "attilan-test-audience")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://api_worker_login:unit_test_password@localhost:5432/opencase_test",
)


def issue_token(user_id: uuid.UUID, clearances: list[str]) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(user_id),
            "clearances": clearances,
            "iat": now,
            "exp": now + timedelta(minutes=5),
            "iss": os.environ["JWT_ISSUER"],
            "aud": os.environ["JWT_AUDIENCE"],
        },
        os.environ["JWT_SECRET_KEY"],
        algorithm="HS256",
    )


def auth_headers(user_id: uuid.UUID, clearances: list[str]) -> dict[str, str]:
    return {"Authorization": f"Bearer {issue_token(user_id, clearances)}"}
