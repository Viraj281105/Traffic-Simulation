"""UrbanFlow V3 client: robustness experiments, packages and tokens over ``/api/v3`` (standard library only).

Authentication is a personal access token (PAT) sent as ``Authorization: Bearer <token>``. A PAT is created
in a signed-in browser session, never by this client, and it is shown once. The shared infrastructure API
key (``X-API-Key``) is **not** something a distributed client should hold; ``api_key`` exists only for
trusted deployments that run the client inside the private network.

Credentials never appear in ``repr``, logs or exception messages, are only sent over HTTPS (plain HTTP is
accepted for loopback addresses, or with ``allow_insecure=True``), and are never forwarded on a redirect:
redirects are refused.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple, Union

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
    WaitTimeout,
)

__all__ = ["Client", "Response", "TERMINAL_STATUSES"]

DEFAULT_TIMEOUT = 30.0
DEFAULT_MAX_RESPONSE_BYTES = 64 * 1024 * 1024
MAX_PACKAGE_BYTES = (
    10 * 1024 * 1024
)  # the server's limit; refused locally before uploading
TOKEN_PREFIX = "uf_pat_"
TERMINAL_STATUSES = frozenset({"completed", "failed", "cancelled"})
_LOOPBACK = frozenset({"localhost", "127.0.0.1", "::1"})
_RETRYABLE = frozenset({429, 502, 503, 504})
_MAX_RETRY_WAIT = 30.0
_MAX_MESSAGE = 300


@dataclass(frozen=True)
class Response:
    status: int
    headers: Mapping[str, str]
    body: bytes


Transport = Callable[
    [str, str, Mapping[str, str], Optional[bytes], float, int], Response
]


class _Secret:
    """Holds a credential so that ``repr``, ``str`` and ``vars()`` dumps never show it."""

    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        self._value = value

    def reveal(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return "<secret>"

    __str__ = __repr__

    def __reduce__(self) -> Any:
        raise TypeError("credentials cannot be pickled")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None  # the 3xx is returned as an error; the Authorization header goes nowhere else


def _urllib_transport(
    method: str,
    url: str,
    headers: Mapping[str, str],
    body: Optional[bytes],
    timeout: float,
    max_bytes: int,
) -> Response:
    request = urllib.request.Request(
        url, data=body, method=method, headers=dict(headers)
    )
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(request, timeout=timeout) as reply:
            return Response(
                reply.status, dict(reply.headers.items()), _read(reply, max_bytes)
            )
    except urllib.error.HTTPError as err:
        try:
            return Response(err.code, dict(err.headers.items()), _read(err, max_bytes))
        finally:
            err.close()
    except TimeoutError as err:
        raise RequestTimeout(f"no answer within {timeout:g} s") from err
    except urllib.error.URLError as err:
        if isinstance(err.reason, TimeoutError):
            raise RequestTimeout(f"no answer within {timeout:g} s") from err
        raise TransportError(
            f"could not reach the server ({type(err.reason).__name__})"
        ) from err
    except OSError as err:
        raise TransportError(
            f"could not reach the server ({type(err).__name__})"
        ) from err


def _read(handle: Any, max_bytes: int) -> bytes:
    chunks: List[bytes] = []
    total = 0
    while True:
        chunk = handle.read(64 * 1024)
        if not chunk:
            return b"".join(chunks)
        total += len(chunk)
        if total > max_bytes:
            raise ResponseTooLarge(f"the reply is larger than {max_bytes:,} bytes")
        chunks.append(chunk)


def _clean(text: str, secrets: List[str]) -> str:
    for secret in secrets:
        if secret:
            text = text.replace(secret, "***")
    text = "".join(ch if ch.isprintable() else " " for ch in text)
    return text[:_MAX_MESSAGE]


class Client:
    """A connection to one UrbanFlow server.

    ``Client("https://urbanflow.example", token=os.environ["URBANFLOW_TOKEN"])``; with no arguments the
    ``URBANFLOW_URL`` and ``URBANFLOW_TOKEN`` environment variables are used."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        token: Optional[str] = None,
        *,
        api_key: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT,
        max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
        allow_insecure: bool = False,
        retries: int = 2,
        transport: Optional[Transport] = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        url = (base_url or os.environ.get("URBANFLOW_URL") or "").strip()
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise ConfigurationError(
                "base_url must be an http(s) URL such as https://host[:port]"
            )
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ConfigurationError(
                "base_url must not contain credentials, a query or a fragment"
            )
        raw_token = (
            token if token is not None else os.environ.get("URBANFLOW_TOKEN", "")
        )
        raw_token = raw_token.strip()
        if raw_token and not raw_token.startswith(TOKEN_PREFIX):
            raise ConfigurationError(
                f"a personal access token starts with {TOKEN_PREFIX!r}"
            )
        raw_key = (
            api_key if api_key is not None else os.environ.get("URBANFLOW_API_KEY", "")
        ).strip()
        secure = (
            parsed.scheme == "https" or parsed.hostname in _LOOPBACK or allow_insecure
        )
        if (raw_token or raw_key) and not secure:
            raise ConfigurationError(
                "refusing to send credentials over plain HTTP; use https:// "
                "(or allow_insecure=True on a network you trust)"
            )
        if timeout <= 0 or retries < 0 or max_response_bytes <= 0:
            raise ConfigurationError(
                "timeout, retries and max_response_bytes must be positive"
            )
        self._base = f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}"
        self._token = _Secret(raw_token)
        self._api_key = _Secret(raw_key)
        self.timeout = float(timeout)
        self.max_response_bytes = int(max_response_bytes)
        self.retries = int(retries)
        self._transport: Transport = transport or _urllib_transport
        self._sleep = sleep

    def __repr__(self) -> str:
        return f"Client(base_url={self._base!r}, token={'set' if self._token.reveal() else 'unset'})"

    # ---- plumbing ----------------------------------------------------------------------------------
    def _headers(self, content_type: Optional[str]) -> Dict[str, str]:
        headers = {"Accept": "application/json", "User-Agent": "urbanflow-client/1.0"}
        token = self._token.reveal()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        key = self._api_key.reveal()
        if key:
            headers["X-API-Key"] = key
        if content_type:
            headers["Content-Type"] = content_type
        return headers

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: Any = None,
        raw_body: Optional[bytes] = None,
        accept_binary: bool = False,
    ) -> Response:
        if not self._token.reveal():
            raise ConfigurationError(
                "no personal access token: pass token=... or set URBANFLOW_TOKEN"
            )
        if json_body is not None:
            body: Optional[bytes] = json.dumps(json_body).encode("utf-8")
            content_type: Optional[str] = "application/json"
        elif raw_body is not None:
            body, content_type = raw_body, "application/octet-stream"
        else:
            body, content_type = None, None
        headers = self._headers(content_type)
        if accept_binary:
            headers["Accept"] = "application/zip, application/json"
        url = self._base + path
        attempts = 1 + (
            self.retries if method == "GET" else 0
        )  # only reads are retried
        for attempt in range(attempts):
            reply = self._transport(
                method, url, headers, body, self.timeout, self.max_response_bytes
            )
            if reply.status in _RETRYABLE and attempt + 1 < attempts:
                self._sleep(
                    min(_retry_after(reply) or 1.0 * (attempt + 1), _MAX_RETRY_WAIT)
                )
                continue
            break
        if reply.status >= 300:  # redirects are refused, so a 3xx is an error too
            raise self._error(reply, method, path)
        return reply

    def _error(self, reply: Response, method: str, path: str) -> ApiError:
        secrets = [self._token.reveal(), self._api_key.reveal()]
        message, code, details = f"HTTP {reply.status}", None, None
        try:
            payload = json.loads(reply.body.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            payload = None
        if isinstance(payload, dict):
            envelope = payload.get("error")
            if isinstance(envelope, dict):
                message = str(envelope.get("message") or message)
                code, details = envelope.get("code"), envelope.get("details")
            elif "detail" in payload:
                details = payload["detail"]
                message = (
                    details
                    if isinstance(details, str)
                    else "; ".join(str(e) for e in (details or {}).get("errors", []))
                    if isinstance(details, dict) and details.get("errors")
                    else message
                )
        kwargs: Dict[str, Any] = dict(
            method=method,
            path=path,
            code=str(code) if code else None,
            details=details,
            retry_after=_retry_after(reply),
        )
        cleaned = _clean(str(message), secrets)
        status = reply.status
        for statuses, cls in _ERRORS:
            if status in statuses:
                return cls(status, cleaned, **kwargs)
        if status >= 500:
            return ServerError(status, cleaned, **kwargs)
        return ApiError(status, cleaned, **kwargs)

    def _json(self, method: str, path: str, **kwargs: Any) -> Dict[str, Any]:
        reply = self._request(method, path, **kwargs)
        try:
            document = json.loads(reply.body.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as err:
            raise ApiError(
                reply.status, "the server sent a reply that is not JSON"
            ) from err
        if not isinstance(document, dict):
            raise ApiError(reply.status, "the server sent an unexpected reply")
        return document

    @staticmethod
    def _id(value: str) -> str:
        if not isinstance(value, str) or not re.fullmatch(
            r"[A-Za-z0-9_-]{1,64}", value
        ):
            raise ConfigurationError("an id is 1-64 letters, digits, '_' or '-'")
        return value

    # ---- server ------------------------------------------------------------------------------------
    def capabilities(self) -> Dict[str, Any]:
        """Features, documents, quotas and limits the server offers."""
        return self._json("GET", "/api/v3/capabilities")

    # ---- experiments -------------------------------------------------------------------------------
    def validate(self, experiment: Mapping[str, Any]) -> Dict[str, Any]:
        """Check an experiment request without running it."""
        return self._json(
            "POST", "/api/v3/experiments/validate", json_body=dict(experiment)
        )

    def submit(self, experiment: Mapping[str, Any]) -> Dict[str, Any]:
        """Queue an experiment; returns its status document (``id``, ``status``, ...)."""
        return self._json("POST", "/api/v3/experiments", json_body=dict(experiment))

    def status(self, experiment_id: str) -> Dict[str, Any]:
        return self._json("GET", f"/api/v3/experiments/{self._id(experiment_id)}")

    def list_experiments(self, limit: int = 25, offset: int = 0) -> Dict[str, Any]:
        return self._json(
            "GET", f"/api/v3/experiments?limit={int(limit)}&offset={int(offset)}"
        )

    def result(self, experiment_id: str) -> Dict[str, Any]:
        """The result of a completed experiment, or the partial result of a cancelled one."""
        return self._json(
            "GET", f"/api/v3/experiments/{self._id(experiment_id)}/result"
        )

    def delete(self, experiment_id: str) -> None:
        self._json("DELETE", f"/api/v3/experiments/{self._id(experiment_id)}")

    def cancel(self, experiment_id: str) -> Dict[str, Any]:
        """Stop a queued or running experiment. Repeating it is harmless."""
        return self._json(
            "POST", f"/api/v3/experiments/{self._id(experiment_id)}/cancel"
        )

    def resume(self, experiment_id: str) -> Dict[str, Any]:
        """Run the unfinished part of a cancelled experiment."""
        return self._json(
            "POST", f"/api/v3/experiments/{self._id(experiment_id)}/resume"
        )

    def wait(
        self,
        experiment_id: str,
        *,
        poll_interval: float = 2.0,
        timeout: Optional[float] = 3600.0,
        on_progress: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        """Poll until the experiment is completed, failed or cancelled and return its status.

        ``on_progress`` receives each status document. Raises :class:`WaitTimeout` after ``timeout``
        seconds (the experiment keeps running)."""
        started = time.monotonic()
        while True:
            status = self.status(experiment_id)
            if on_progress is not None:
                on_progress(status)
            if status.get("status") in TERMINAL_STATUSES:
                return status
            waited = time.monotonic() - started
            if timeout is not None and waited >= timeout:
                raise WaitTimeout(experiment_id, str(status.get("status")), timeout)
            self._sleep(max(0.05, poll_interval))

    def run(
        self,
        experiment: Mapping[str, Any],
        *,
        poll_interval: float = 2.0,
        timeout: Optional[float] = 3600.0,
        on_progress: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        """Submit, wait and return the result. Raises ``Conflict`` if it did not complete."""
        accepted = self.submit(experiment)
        self.wait(
            accepted["id"],
            poll_interval=poll_interval,
            timeout=timeout,
            on_progress=on_progress,
        )
        return self.result(accepted["id"])

    # ---- packages ----------------------------------------------------------------------------------
    def export_package(
        self,
        experiment_id: str,
        path: Union[str, Path, None] = None,
        *,
        overwrite: bool = False,
    ) -> bytes:
        """Download a completed experiment as ``.ufpkg`` bytes; also write them to ``path`` if given.

        An existing file is never replaced unless ``overwrite=True``."""
        reply = self._request(
            "GET",
            f"/api/v3/experiments/{self._id(experiment_id)}/package",
            accept_binary=True,
        )
        if path is not None:
            target = Path(path)
            mode = "wb" if overwrite else "xb"
            try:
                with open(target, mode) as handle:
                    handle.write(reply.body)
            except FileExistsError as err:
                raise ConfigurationError(f"{target.name} already exists") from err
        return reply.body

    def verify_package(self, package: Union[bytes, str, Path]) -> Dict[str, Any]:
        """Have the server check a ``.ufpkg`` (bytes or a file). Nothing is run or stored.

        The report's ``internallyConsistent`` says whether the package is internally consistent; it does
        not say who made it."""
        if isinstance(package, (bytes, bytearray)):
            data = bytes(package)
        else:
            source = Path(package)
            size = source.stat().st_size
            if size > MAX_PACKAGE_BYTES:
                raise ConfigurationError(
                    f"a package is at most {MAX_PACKAGE_BYTES:,} bytes"
                )
            data = source.read_bytes()
        if len(data) > MAX_PACKAGE_BYTES:
            raise ConfigurationError(
                f"a package is at most {MAX_PACKAGE_BYTES:,} bytes"
            )
        return self._json("POST", "/api/v3/packages/verify", raw_body=data)

    # ---- experiment copilot ------------------------------------------------------------------------
    def copilot_catalogue(self) -> Dict[str, Any]:
        """What a Copilot proposal may contain (alternatives, profiles, demand levels, bounds, quotas)."""
        return self._json("GET", "/api/v3/copilot/catalogue")

    def propose(self, question: str, *, deterministic: bool = False) -> Dict[str, Any]:
        """Turn a research question into a validated experiment proposal. Nothing runs yet.

        ``deterministic=True`` skips the language model even when the server has one."""
        body = {
            "question": question,
            "mode": "deterministic" if deterministic else "auto",
        }
        return self._json("POST", "/api/v3/copilot/proposals", json_body=body)

    def proposal(self, proposal_id: str) -> Dict[str, Any]:
        return self._json("GET", f"/api/v3/copilot/proposals/{self._id(proposal_id)}")

    def apply_suggestion(self, proposal_id: str, code: str) -> Dict[str, Any]:
        """A new proposal with one of the validation suggestions applied (validated again)."""
        return self._json(
            "POST",
            f"/api/v3/copilot/proposals/{self._id(proposal_id)}/suggestions/{self._id(code)}",
        )

    def confirm_proposal(self, proposal: Mapping[str, Any]) -> Dict[str, Any]:
        """Submit a proposal you have inspected. Needs its id and content hash; works once."""
        return self._json(
            "POST",
            f"/api/v3/copilot/proposals/{self._id(str(proposal['id']))}/confirm",
            json_body={"contentHash": proposal["contentHash"]},
        )

    def interpret(
        self,
        experiment_id: str,
        *,
        preferred: Optional[str] = None,
        template_only: bool = False,
    ) -> Dict[str, Any]:
        """Measured evidence plus a template summary and, if it passes grounding, a model-written reading."""
        body = {"preferred": preferred, "mode": "template" if template_only else "auto"}
        return self._json(
            "POST",
            f"/api/v3/copilot/experiments/{self._id(experiment_id)}/interpretation",
            json_body=body,
        )

    # ---- discovery lab -----------------------------------------------------------------------------
    def estimate_search(self, spec: Mapping[str, Any]) -> Dict[str, Any]:
        """Runs and simulated seconds a Discovery search would reserve (starts nothing)."""
        return self._json("POST", "/api/v3/discovery/estimate", json_body=dict(spec))

    def start_search(self, spec: Mapping[str, Any]) -> Dict[str, Any]:
        """Start a bounded Discovery search (an EXPERIMENTAL evolutionary search, not a learned model)."""
        return self._json("POST", "/api/v3/discovery/searches", json_body=dict(spec))

    def list_searches(self) -> List[Dict[str, Any]]:
        reply = self._request("GET", "/api/v3/discovery/searches")
        document = json.loads(reply.body.decode("utf-8"))
        return list(document) if isinstance(document, list) else []

    def search_status(self, search_id: str) -> Dict[str, Any]:
        return self._json("GET", f"/api/v3/discovery/searches/{self._id(search_id)}")

    def search_result(self, search_id: str) -> Dict[str, Any]:
        return self._json(
            "GET", f"/api/v3/discovery/searches/{self._id(search_id)}/result"
        )

    def cancel_search(self, search_id: str) -> Dict[str, Any]:
        return self._json(
            "POST", f"/api/v3/discovery/searches/{self._id(search_id)}/cancel"
        )

    def export_search_package(
        self,
        search_id: str,
        path: Union[str, Path, None] = None,
        *,
        overwrite: bool = False,
    ) -> bytes:
        reply = self._request(
            "GET",
            f"/api/v3/discovery/searches/{self._id(search_id)}/package",
            accept_binary=True,
        )
        if path is not None:
            try:
                with open(Path(path), "wb" if overwrite else "xb") as handle:
                    handle.write(reply.body)
            except FileExistsError as err:
                raise ConfigurationError(f"{Path(path).name} already exists") from err
        return reply.body

    # ---- tokens ------------------------------------------------------------------------------------
    def list_tokens(self) -> List[Dict[str, Any]]:
        """Your active tokens (needs the ``tokens:read`` scope). The secrets are never listed."""
        return list(self._json("GET", "/api/v3/tokens").get("tokens", []))

    def revoke_token(self, token_id: str) -> None:
        """Revoke one of your tokens at once (needs ``tokens:manage``)."""
        self._json("DELETE", f"/api/v3/tokens/{self._id(token_id)}")


def _retry_after(reply: Response) -> Optional[float]:
    for key, value in reply.headers.items():
        if key.lower() == "retry-after":
            try:
                return max(0.0, float(value))
            except ValueError:
                return None
    return None


_ERRORS: List[Tuple[frozenset[int], type[ApiError]]] = [
    (frozenset({401}), AuthenticationError),
    (frozenset({403}), PermissionDenied),
    (frozenset({404}), NotFound),
    (frozenset({409}), Conflict),
    (frozenset({413}), PayloadTooLarge),
    (frozenset({422}), InvalidRequest),
    (frozenset({429}), QuotaExceeded),
]
