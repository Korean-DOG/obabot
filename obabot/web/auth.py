"""JWT authentication middleware for obabot web layer."""

import logging
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


def create_auth_middleware(secret_key: str) -> Callable:
    """Create a FastAPI middleware that validates JWT tokens.

    When enabled, every request to the API must include
    ``Authorization: Bearer <token>`` header.  The ``user_id`` claim
    from the token overrides the ``user_id`` field in the request body
    for security.

    Args:
        secret_key: HMAC secret used to sign/verify tokens.

    Returns:
        An ASGI middleware callable suitable for ``app.middleware("http")``.
    """
    try:
        import jwt as pyjwt
    except ImportError:
        raise ImportError(
            "PyJWT is required for auth_config support. "
            "Install it with: pip install PyJWT"
        )

    async def middleware(request: Any, call_next: Callable) -> Any:
        from starlette.responses import JSONResponse

        auth_header: Optional[str] = request.headers.get("authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                {"detail": "Missing or invalid Authorization header"},
                status_code=401,
            )

        token = auth_header[len("Bearer "):]
        try:
            payload: Dict[str, Any] = pyjwt.decode(
                token, secret_key, algorithms=["HS256"],
            )
        except pyjwt.ExpiredSignatureError:
            return JSONResponse({"detail": "Token expired"}, status_code=401)
        except pyjwt.InvalidTokenError as exc:
            logger.debug("[web auth] invalid token: %s", exc)
            return JSONResponse({"detail": "Invalid token"}, status_code=401)

        request.state.jwt_payload = payload
        request.state.jwt_user_id = payload.get("user_id")

        response = await call_next(request)
        return response

    return middleware


def generate_token(
    user_id: int,
    secret_key: str,
    expires_delta: Optional[int] = None,
    extra_claims: Optional[Dict[str, Any]] = None,
) -> str:
    """Generate a JWT token for the given user.

    Args:
        user_id: Numeric user identifier (embedded as ``user_id`` claim).
        secret_key: HMAC secret.
        expires_delta: Lifetime in seconds (default: 24 hours).
        extra_claims: Additional claims to embed in the token.

    Returns:
        Encoded JWT string.
    """
    import time

    try:
        import jwt as pyjwt
    except ImportError:
        raise ImportError("PyJWT is required: pip install PyJWT")

    now = int(time.time())
    payload: Dict[str, Any] = {
        "user_id": user_id,
        "iat": now,
        "exp": now + (expires_delta or 86400),
    }
    if extra_claims:
        payload.update(extra_claims)

    return pyjwt.encode(payload, secret_key, algorithm="HS256")
