"""Python client for the UrbanFlow V3 API (robustness experiments, ``.ufpkg`` packages, tokens)."""

from .client import TERMINAL_STATUSES, Client, Response
from .errors import (
    ApiError,
    AuthenticationError,
    ConfigurationError,
    Conflict,
    InvalidRequest,
    NotFound,
    PayloadTooLarge,
    PermissionDenied,
    QuotaExceeded,
    RequestTimeout,
    ResponseTooLarge,
    ServerError,
    TransportError,
    UrbanFlowError,
    WaitTimeout,
)

__version__ = "1.0.0"

__all__ = [
    "ApiError",
    "AuthenticationError",
    "Client",
    "Conflict",
    "ConfigurationError",
    "InvalidRequest",
    "NotFound",
    "PayloadTooLarge",
    "PermissionDenied",
    "QuotaExceeded",
    "RequestTimeout",
    "Response",
    "ResponseTooLarge",
    "ServerError",
    "TERMINAL_STATUSES",
    "TransportError",
    "UrbanFlowError",
    "WaitTimeout",
    "__version__",
]
