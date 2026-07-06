"""
app/api/routes/oauth.py
───────────────────────
OAuth 2.1 Authorization Server endpoints for DataBridge.

These endpoints allow MCP clients (e.g., OpenWebUI) to authenticate via the
standard Authorization Code flow with PKCE.  The FastMCP OAuthProxy acts as
a bridge: it redirects users here to log in, then exchanges the resulting
authorization code for a DataBridge JWT.

Endpoints
---------
GET  /oauth/authorize   → show login form (browser redirect from OAuthProxy)
POST /oauth/authorize   → validate credentials, issue auth code, redirect back
POST /oauth/token       → exchange auth code for DataBridge access token
"""
from __future__ import annotations

import hashlib
import base64
import json
import logging
import secrets
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

import redis.asyncio as aioredis

from app.core.config import settings
from app.core.database import get_db, AsyncSessionLocal
from app.core.security import verify_password, create_access_token
from app.models import User

logger = logging.getLogger(__name__)

router = APIRouter()

# ── Redis helpers ─────────────────────────────────────────────────────────────
_redis_client: aioredis.Redis | None = None
AUTH_CODE_TTL = 300  # 5 minutes
AUTH_CODE_PREFIX = "oauth:code:"


async def _get_redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client


# ── Login page HTML ──────────────────────────────────────────────────────────
def _render_login_page(
    *,
    client_id: str = "",
    redirect_uri: str = "",
    state: str = "",
    scope: str = "",
    code_challenge: str = "",
    code_challenge_method: str = "",
    error: str = "",
) -> HTMLResponse:
    """Return a self-contained HTML login page with DataBridge branding."""
    error_html = ""
    if error:
        error_html = f"""
        <div class="error-banner">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" style="flex-shrink:0;">
                <circle cx="8" cy="8" r="7" stroke="#b91c1c" stroke-width="1.5"/>
                <path d="M8 4.5v4" stroke="#b91c1c" stroke-width="1.5" stroke-linecap="round"/>
                <circle cx="8" cy="11" r="0.75" fill="#b91c1c"/>
            </svg>
            {error}
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>DataBridge — Sign In</title>
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet" />
    <style>
        *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            background: #faf9f5;
            color: #1b1c1a;
        }}
        .card {{
            background: #ffffff;
            border: 1px solid #E8E6DF;
            border-radius: 16px;
            padding: 44px 40px 36px;
            width: 100%;
            max-width: 420px;
            box-shadow: 0 4px 12px -2px rgba(26, 25, 22, 0.05);
        }}
        .logo {{
            text-align: center;
            margin-bottom: 32px;
        }}
        .logo-icon {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 48px;
            height: 48px;
            background: #eef4f5;
            border-radius: 12px;
            margin-bottom: 16px;
        }}
        .logo-icon svg {{
            width: 26px;
            height: 26px;
        }}
        .logo h1 {{
            font-size: 22px;
            font-weight: 800;
            color: #1b1c1a;
            letter-spacing: -0.02em;
        }}
        .logo p {{
            font-size: 13px;
            color: #6B6A65;
            margin-top: 6px;
            line-height: 1.5;
        }}
        .form-group {{
            margin-bottom: 18px;
        }}
        label {{
            display: block;
            font-size: 12px;
            font-weight: 600;
            color: #494740;
            margin-bottom: 6px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        input[type="email"], input[type="password"] {{
            width: 100%;
            padding: 10px 14px;
            border: 1px solid #E8E6DF;
            border-radius: 8px;
            background: #f4f4f0;
            color: #1b1c1a;
            font-family: inherit;
            font-size: 14px;
            outline: none;
            transition: border-color 0.2s, box-shadow 0.2s;
        }}
        input:focus {{
            border-color: #48757c;
            box-shadow: 0 0 0 2px rgba(72, 117, 124, 0.15);
        }}
        input::placeholder {{
            color: #7a776f;
        }}
        button {{
            width: 100%;
            padding: 12px;
            border: none;
            border-radius: 8px;
            background: #48757c;
            color: #ffffff;
            font-family: inherit;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: opacity 0.2s, transform 0.1s;
            margin-top: 6px;
        }}
        button:hover {{ opacity: 0.9; }}
        button:active {{ transform: scale(0.99); }}
        .footer {{
            text-align: center;
            margin-top: 24px;
            font-size: 11px;
            font-weight: 500;
            color: #7a776f;
            letter-spacing: 0.03em;
        }}
        .error-banner {{
            display: flex;
            align-items: center;
            gap: 10px;
            background: #fef2f2;
            border: 1px solid #fecaca;
            color: #991b1b;
            padding: 10px 14px;
            border-radius: 8px;
            margin-bottom: 20px;
            font-size: 13px;
            line-height: 1.4;
        }}
        .divider {{
            height: 1px;
            background: #E8E6DF;
            margin: 24px 0;
        }}
    </style>
</head>
<body>
    <div class="card">
        <div class="logo">
            <div class="logo-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="#48757c" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M12 2L2 7l10 5 10-5-10-5z"/>
                    <path d="M2 17l10 5 10-5"/>
                    <path d="M2 12l10 5 10-5"/>
                </svg>
            </div>
            <h1>DataBridge</h1>
            <p>Sign in to continue to your MCP session</p>
        </div>
        {error_html}
        <form method="post" action="/oauth/authorize">
            <div class="form-group">
                <label for="email">Email</label>
                <input type="email" id="email" name="email" placeholder="you@company.com" required autofocus />
            </div>

            <div class="form-group">
                <label for="password">Password</label>
                <input type="password" id="password" name="password" placeholder="••••••••" required />
            </div>

            <input type="hidden" name="client_id" value="{client_id}" />
            <input type="hidden" name="redirect_uri" value="{redirect_uri}" />
            <input type="hidden" name="state" value="{state}" />
            <input type="hidden" name="scope" value="{scope}" />
            <input type="hidden" name="code_challenge" value="{code_challenge}" />
            <input type="hidden" name="code_challenge_method" value="{code_challenge_method}" />

            <button type="submit">Sign In</button>
        </form>
        <div class="divider"></div>
        <div class="footer">Secured by DataBridge OAuth 2.1</div>
    </div>
</body>
</html>"""
    return HTMLResponse(content=html)


# ── GET /oauth/authorize ─────────────────────────────────────────────────────
@router.get("/oauth/authorize")
async def authorize_get(
    request: Request,
    response_type: str = "code",
    client_id: str = "",
    redirect_uri: str = "",
    state: str = "",
    scope: str = "",
    code_challenge: str = "",
    code_challenge_method: str = "",
):
    """
    Renders the DataBridge login page.

    The OAuthProxy redirects the user's browser here.  After the user submits
    valid credentials (handled by the POST endpoint below), an authorization
    code is generated and the user is redirected back to the OAuthProxy
    callback URI.
    """
    if response_type != "code":
        return JSONResponse(
            {"error": "unsupported_response_type"},
            status_code=400,
        )

    return _render_login_page(
        client_id=client_id,
        redirect_uri=redirect_uri,
        state=state,
        scope=scope,
        code_challenge=code_challenge,
        code_challenge_method=code_challenge_method,
    )


# ── POST /oauth/authorize ────────────────────────────────────────────────────
@router.post("/oauth/authorize")
async def authorize_post(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    client_id: str = Form(""),
    redirect_uri: str = Form(""),
    state: str = Form(""),
    scope: str = Form(""),
    code_challenge: str = Form(""),
    code_challenge_method: str = Form(""),
    db: AsyncSession = Depends(get_db),
):
    """
    Validates the user's credentials and, on success, issues a short-lived
    authorization code stored in Redis.  Redirects to *redirect_uri* with
    ``?code=...&state=...``.
    """
    # ── validate credentials ──────────────────────────────────────────────
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(password, user.hashed_password):
        return _render_login_page(
            client_id=client_id,
            redirect_uri=redirect_uri,
            state=state,
            scope=scope,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
            error="Invalid email or password.",
        )

    if not user.is_active:
        return _render_login_page(
            client_id=client_id,
            redirect_uri=redirect_uri,
            state=state,
            scope=scope,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
            error="This account has been deactivated.",
        )

    # ── generate authorization code ───────────────────────────────────────
    code = secrets.token_urlsafe(48)

    code_data = json.dumps({
        "user_id": str(user.id),
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "code_challenge": code_challenge,
        "code_challenge_method": code_challenge_method,
    })

    r = await _get_redis()
    await r.setex(f"{AUTH_CODE_PREFIX}{code}", AUTH_CODE_TTL, code_data)

    logger.info("OAuth code issued for user=%s client=%s", user.email, client_id)

    # ── redirect back to caller (OAuthProxy callback) ─────────────────────
    params: dict[str, str] = {"code": code}
    if state:
        params["state"] = state

    separator = "&" if "?" in redirect_uri else "?"
    return RedirectResponse(
        url=f"{redirect_uri}{separator}{urlencode(params)}",
        status_code=302,
    )


# ── POST /oauth/token ────────────────────────────────────────────────────────
@router.post("/oauth/token")
async def token_exchange(request: Request):
    """
    OAuth Token endpoint — exchanges an authorization code for an access token.

    The OAuthProxy calls this endpoint server-side after receiving the auth
    code at its callback.  We validate the code (and PKCE if present), then
    issue a standard DataBridge HS256 JWT.
    """
    # ── parse request body (form or JSON) ─────────────────────────────────
    content_type = request.headers.get("content-type", "")
    if "application/x-www-form-urlencoded" in content_type:
        form = await request.form()
        data = dict(form)
    elif "application/json" in content_type:
        data = await request.json()
    else:
        data = dict(request.query_params)

    grant_type = data.get("grant_type", "")
    code = data.get("code", "")
    redirect_uri = data.get("redirect_uri", "")
    code_verifier = data.get("code_verifier", "")

    if grant_type != "authorization_code":
        return JSONResponse(
            {"error": "unsupported_grant_type"},
            status_code=400,
        )

    if not code:
        return JSONResponse(
            {"error": "invalid_request", "error_description": "Missing code"},
            status_code=400,
        )

    # ── retrieve and consume the code (single-use) ────────────────────────
    r = await _get_redis()
    code_key = f"{AUTH_CODE_PREFIX}{code}"
    code_json = await r.get(code_key)

    if not code_json:
        return JSONResponse(
            {"error": "invalid_grant", "error_description": "Invalid or expired authorization code"},
            status_code=400,
        )

    await r.delete(code_key)  # single-use
    code_data: dict = json.loads(code_json)

    # ── validate redirect_uri ─────────────────────────────────────────────
    if redirect_uri and code_data["redirect_uri"] and redirect_uri != code_data["redirect_uri"]:
        return JSONResponse(
            {"error": "invalid_grant", "error_description": "redirect_uri mismatch"},
            status_code=400,
        )

    # ── validate PKCE ─────────────────────────────────────────────────────
    stored_challenge = code_data.get("code_challenge", "")
    stored_method = code_data.get("code_challenge_method", "")

    if stored_challenge and stored_method:
        if not code_verifier:
            return JSONResponse(
                {"error": "invalid_grant", "error_description": "Missing code_verifier for PKCE"},
                status_code=400,
            )

        if stored_method == "S256":
            computed = (
                base64.urlsafe_b64encode(
                    hashlib.sha256(code_verifier.encode("ascii")).digest()
                )
                .rstrip(b"=")
                .decode("ascii")
            )
            if computed != stored_challenge:
                return JSONResponse(
                    {"error": "invalid_grant", "error_description": "PKCE verification failed"},
                    status_code=400,
                )
        elif stored_method == "plain":
            if code_verifier != stored_challenge:
                return JSONResponse(
                    {"error": "invalid_grant", "error_description": "PKCE verification failed"},
                    status_code=400,
                )

    # ── issue DataBridge JWT ──────────────────────────────────────────────
    user_id = code_data["user_id"]

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user or not user.is_active:
            return JSONResponse(
                {"error": "invalid_grant", "error_description": "User not found or inactive"},
                status_code=400,
            )

        access_token = create_access_token(user)

    logger.info("OAuth token issued for user=%s", user.email)

    return JSONResponse({
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    })
