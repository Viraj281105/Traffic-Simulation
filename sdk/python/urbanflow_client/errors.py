"""Exceptions raised by the UrbanFlow client.

No exception carries a credential: messages are built from the server's reply with every occurrence of the
token and API key removed, and from the request's method and path only (never its headers).
"""

from __future__ import annotations

from typing import Any, List, Optional


class UrbanFlowError(Exception):
    """Base class of every error raised by this package."""


class ConfigurationError(UrbanFlowError, ValueError):
    """The client was set up incorrectly (missing or malformed URL, token or file)."""


class TransportError(UrbanFlowError):
    """The request never produced an HTTP response (connection refused, DNS, TLS)."""


class RequestTimeout(TransportError):
    """The server did not answer within the timeout."""


class ResponseTooLarge(TransportError):
    """The reply was larger than ``max_response_bytes``."""


class WaitTimeout(UrbanFlowError):
    """``wait`` gave up. The experiment is **not** cancelled and may still finish."""

    def __init__(self, experiment_id: str, status: str, seconds: float) -> None:
        super().__init__(
            f"experiment {experiment_id} was still {status!r} after {seconds:g} s"
        )
        self.experiment_id = experiment_id
        self.status = status


class ApiError(UrbanFlowError):
    """The server answered with an error status."""

    def __init__(
        self,
        status: int,
        message: str,
        *,
        method: str = "",
        path: str = "",
        code: Optional[str] = None,
        details: Any = None,
        retry_after: Optional[float] = None,
    ) -> None:
        where = f" ({method} {path})" if method else ""
        super().__init__(f"HTTP {status}{where}: {message}")
        self.status = status
        self.message = message
        self.code = code
        self.details = details
        self.retry_after = retry_after


class AuthenticationError(ApiError):
    """401: no valid credential (missing, unknown, expired or revoked token)."""


class PermissionDenied(ApiError):
    """403: the token lacks a required scope, or the operation is browser-only."""


class NotFound(ApiError):
    """404: no such experiment or token, or it belongs to someone else."""


class Conflict(ApiError):
    """409: the request is not possible in the experiment's current state."""


class PayloadTooLarge(ApiError):
    """413: the request or package is over a size limit."""


class InvalidRequest(ApiError):
    """422: the request was understood but is not valid; ``errors`` lists every problem."""

    @property
    def errors(self) -> List[str]:
        detail = self.details
        if isinstance(detail, dict) and isinstance(detail.get("errors"), list):
            return [str(e) for e in detail["errors"]]
        return [self.message]


class QuotaExceeded(ApiError):
    """429: a quota or rate limit; ``retry_after`` is the server's hint in seconds, when given."""


class ServerError(ApiError):
    """5xx: the server failed."""
