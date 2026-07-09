"""
app/mcp.py
----------
DataBridge FastMCP Server -- 9 tools across read/write/federated categories.
"""
import logging
from fastmcp import FastMCP
from fastmcp.server.auth.providers.azure import AzureProvider
from starlette.responses import RedirectResponse
from fastapi import Request

from app.core.config import settings
from app.core.prompts import SYSTEM_INSTRUCTIONS
from app.tools.mcp_tools import register_mcp_tools

# Monkeypatch validate_issuer_url to allow HTTP URLs for non-localhost in development
try:
    import mcp.server.auth.routes
    mcp.server.auth.routes.validate_issuer_url = lambda url: None
except ImportError:
    pass

logger = logging.getLogger(__name__)

from mcp.server.auth.provider import AccessToken

class CustomAzureProvider(AzureProvider):
    """Rewrites callback redirects to include the :8091 port for Open WebUI."""
    async def _handle_idp_callback(self, request: Request):
        response = await super()._handle_idp_callback(request)
        if isinstance(response, RedirectResponse):
            location = response.headers.get("location", "")
            if "https://chat.synovergetech.com/oauth/clients/" in location:
                new_location = location.replace(
                    "https://chat.synovergetech.com/oauth/clients/",
                    "https://chat.synovergetech.com:8091/oauth/clients/"
                )
                response.headers["location"] = new_location
        return response

    async def verify_token(self, token: str) -> AccessToken | None:
        """Allow local backend JWT tokens to bypass Microsoft Azure verification."""
        try:
            from app.core.security import decode_token
            payload = decode_token(token)
            if payload and "sub" in payload:
                return AccessToken(
                    token=token,
                    client_id="databridge-backend-client",
                    scopes=["MsSsoMvcScope.Read"],
                    expires_at=payload.get("exp"),
                    claims=payload,
                )
        except Exception:
            pass

        return await super().verify_token(token)


logger.info("Initializing FastMCP AzureProvider for Microsoft SSO (Tenant: %s)", settings.MICROSOFT_TENANT_ID)
auth = CustomAzureProvider(
    client_id=settings.MICROSOFT_CLIENT_ID,
    client_secret=settings.MICROSOFT_CLIENT_SECRET,
    tenant_id=settings.MICROSOFT_TENANT_ID,
    base_url=settings.MCP_BASE_URL,
    required_scopes=["MsSsoMvcScope.Read"],
    additional_authorize_scopes=["User.Read", "openid", "profile", "email"],
    require_authorization_consent=False,
    allowed_client_redirect_uris=[
        "http://localhost:*",
        "http://127.0.0.1:*",
        "https://chat.synovergetech.com:8091/*",
        "https://chat.synovergetech.com/*",
    ],
)

mcp = FastMCP(
    "DataBridge",
    auth=auth,
    instructions=SYSTEM_INSTRUCTIONS,
)

register_mcp_tools(mcp)

if __name__ == "__main__":
    import uvicorn
    app = mcp.http_app(path="/")


    # Path rewriter middleware: seamlessly route both / and /mcp requests from OpenWebUI to root
    @app.middleware("http")
    async def rewrite_mcp_path(request: Request, call_next):
        if request.scope["path"] == "/mcp" or request.scope["path"].startswith("/mcp/"):
            request.scope["path"] = request.scope["path"][4:] or "/"
        return await call_next(request)

    uvicorn.run(app, host="0.0.0.0", port=9000)
