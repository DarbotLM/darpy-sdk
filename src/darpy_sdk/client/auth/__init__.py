"""OAuth2 Authentication implementation for httpx2.

Implements authorization code flow with PKCE and automatic token refresh.
"""

from darpy_sdk.client.auth.exceptions import OAuthFlowError, OAuthRegistrationError, OAuthTokenError
from darpy_sdk.client.auth.oauth2 import (
    OAuthClientProvider,
    PKCEParameters,
    TokenStorage,
)
from darpy_sdk.shared.auth import AuthorizationCodeResult

__all__ = [
    "AuthorizationCodeResult",
    "OAuthClientProvider",
    "OAuthFlowError",
    "OAuthRegistrationError",
    "OAuthTokenError",
    "PKCEParameters",
    "TokenStorage",
]
