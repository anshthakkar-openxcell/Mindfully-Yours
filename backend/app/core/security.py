"""
Service-to-service authentication for the AI service's API.

Per documnets/understanding/14_FEATURE_BREAKDOWN_AND_IMPLEMENTATION_PLAN.md §4, this API is called
by the (out-of-scope) NestJS backend, not directly by end-user clients. The AI service TRUSTS the
caller's consent-check result -- it does not re-verify consent itself (that's the backend's job,
per 02_ARCHITECTURE.md §1). This module only verifies that the CALLER is the legitimate backend
(a shared-secret / service token), not that the end user consented.

TODO: replace the shared-secret placeholder below with whatever service-auth scheme the NestJS
backend team standardizes on (mTLS, signed JWT, etc) before this goes anywhere near production --
this stub exists so the API layer has a single enforcement point to wire that into later.
"""

from fastapi import Header, HTTPException, status

from app.core.config import get_settings


async def verify_service_caller(x_service_token: str = Header(default="")) -> None:
    settings = get_settings()
    expected = getattr(settings, "service_token", "") or ""
    if not expected:
        # No token configured -- allowed only in local development. Fail closed everywhere else.
        if settings.app_env != "development":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Service auth is not configured for this environment.",
            )
        return
    if x_service_token != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid service token."
        )
