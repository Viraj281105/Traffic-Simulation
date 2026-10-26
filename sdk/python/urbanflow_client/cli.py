"""Command line for the UrbanFlow client: ``python -m urbanflow_client <command>``.

The server URL and the token come from ``URBANFLOW_URL`` and ``URBANFLOW_TOKEN`` only: a token on the
command line would end up in shell history and process listings. Output is JSON on stdout; errors go to
stderr. Exit codes: 0 success, 1 the server refused or failed, 2 bad usage or configuration."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional, Sequence

from .client import MAX_PACKAGE_BYTES, Client
from .errors import ApiError, ConfigurationError, UrbanFlowError

MAX_EXPERIMENT_FILE_BYTES = 1024 * 1024


def _load_json(path: str) -> Any:
    source = Path(path)
    if source.stat().st_size > MAX_EXPERIMENT_FILE_BYTES:
        raise ConfigurationError("the experiment file is larger than 1 MiB")
    try:
        return json.loads(source.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, ValueError) as err:
        raise ConfigurationError(f"{source.name} is not valid JSON") from err


def _print(document: Any) -> None:
    json.dump(document, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="urbanflow", description=__doc__.split("\n\n")[0]
    )
    parser.add_argument(
        "--timeout", type=float, default=30.0, help="seconds per request"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("capabilities")
    for name in ("validate", "submit", "run"):
        p = sub.add_parser(name)
        p.add_argument("file", help="experiment JSON file")
    for name in ("status", "result", "cancel", "resume", "delete", "wait"):
        p = sub.add_parser(name)
        p.add_argument("id")
    sub.add_parser("list")
    p = sub.add_parser("export")
    p.add_argument("id")
    p.add_argument("output", help="where to write the .ufpkg (never overwritten)")
    p = sub.add_parser("verify")
    p.add_argument("package")
    tokens = sub.add_parser("tokens")
    tsub = tokens.add_subparsers(dest="action", required=True)
    tsub.add_parser("list")
    p = tsub.add_parser("revoke")
    p.add_argument("id")
    return parser


def main(argv: Optional[Sequence[str]] = None, client: Optional[Client] = None) -> int:
    args = _parser().parse_args(argv)
    try:
        api = client or Client(timeout=args.timeout)
        cmd = args.command
        out: Any
        if cmd == "capabilities":
            out = api.capabilities()
        elif cmd == "validate":
            out = api.validate(_load_json(args.file))
        elif cmd == "submit":
            out = api.submit(_load_json(args.file))
        elif cmd == "run":
            out = api.run(
                _load_json(args.file),
                on_progress=lambda s: print(
                    f"{s.get('status')}: {(s.get('progress') or {}).get('fraction', '')}",
                    file=sys.stderr,
                ),
            )
        elif cmd == "status":
            out = api.status(args.id)
        elif cmd == "result":
            out = api.result(args.id)
        elif cmd == "cancel":
            out = api.cancel(args.id)
        elif cmd == "resume":
            out = api.resume(args.id)
        elif cmd == "delete":
            api.delete(args.id)
            out = {"deleted": args.id}
        elif cmd == "wait":
            out = api.wait(args.id)
        elif cmd == "list":
            out = api.list_experiments()
        elif cmd == "export":
            data = api.export_package(args.id, args.output)
            out = {"written": Path(args.output).name, "bytes": len(data)}
        elif cmd == "verify":
            if Path(args.package).stat().st_size > MAX_PACKAGE_BYTES:
                raise ConfigurationError("a package is at most 10 MiB")
            out = api.verify_package(args.package)
        else:  # tokens
            if args.action == "list":
                out = api.list_tokens()
            else:
                api.revoke_token(args.id)
                out = {"revoked": args.id}
        _print(out)
        if cmd == "verify" and not out.get("internallyConsistent"):
            return 1
        return 0
    except ConfigurationError as err:
        print(f"configuration error: {err}", file=sys.stderr)
        return 2
    except ApiError as err:
        print(f"error: {err}", file=sys.stderr)
        return 1
    except (UrbanFlowError, OSError) as err:
        print(f"error: {type(err).__name__}: {err}", file=sys.stderr)
        return 1
