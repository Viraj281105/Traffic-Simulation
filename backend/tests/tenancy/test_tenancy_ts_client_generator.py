"""scripts/generate_ts_client.py: deterministic, complete, read-only on the snapshot."""

import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
from pathlib import Path
from types import ModuleType
from typing import Any, Dict

import pytest

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "scripts" / "generate_ts_client.py"
SNAPSHOT = REPO / "shared" / "schemas" / "v3" / "openapi.v3.snapshot.json"
METHODS = ("get", "put", "post", "delete", "patch", "options", "head")


def load_generator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("generate_ts_client", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def gen() -> ModuleType:
    return load_generator()


@pytest.fixture(scope="module")
def spec() -> Dict[str, Any]:
    data: Dict[str, Any] = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    return data


def test_output_is_deterministic(gen: ModuleType, spec: Dict[str, Any]) -> None:
    first = gen.generate(spec, SNAPSHOT.name)
    assert first == gen.generate(json.loads(json.dumps(spec)), SNAPSHOT.name)
    assert "\r" not in first
    assert first.endswith("}\n") and not first.endswith("\n\n")


def test_main_writes_the_same_bytes_and_leaves_the_snapshot_alone(
    gen: ModuleType, spec: Dict[str, Any], tmp_path: Path
) -> None:
    before = hashlib.sha256(SNAPSHOT.read_bytes()).hexdigest()
    out_a, out_b = tmp_path / "a" / "x.ts", tmp_path / "b" / "y.ts"
    assert gen.main(["--out", str(out_a)]) == 0
    assert gen.main(["--out", str(out_b)]) == 0
    assert out_a.read_bytes() == out_b.read_bytes()
    assert out_a.read_text(encoding="utf-8") == gen.generate(spec, SNAPSHOT.name)
    assert hashlib.sha256(SNAPSHOT.read_bytes()).hexdigest() == before


def test_default_output_path(gen: ModuleType) -> None:
    assert gen.DEFAULT_OUT == REPO / "clients" / "typescript" / "urbanflow.ts"


def test_every_operation_has_a_function_and_an_index_entry(
    gen: ModuleType, spec: Dict[str, Any]
) -> None:
    text = gen.generate(spec, SNAPSHOT.name)
    expected = [
        (m.upper(), path, op["operationId"])
        for path, item in spec["paths"].items()
        for m, op in item.items()
        if m in METHODS
    ]
    assert expected
    functions = re.findall(r"^export async function (\w+)\(", text, re.M)
    assert len(functions) == len(expected)
    assert len(set(functions)) == len(functions)
    for method, path, op_id in expected:
        assert (
            f'operationId: {json.dumps(op_id)}, method: "{method}", path: {json.dumps(path)}'
            in text
        )
        assert f"/** {method} {path}" in text


def test_every_component_schema_has_a_type(
    gen: ModuleType, spec: Dict[str, Any]
) -> None:
    text = gen.generate(spec, SNAPSHOT.name)
    for name in spec["components"]["schemas"]:
        assert re.search(
            rf"^export (interface|type) {re.escape(name)}\b", text, re.M
        ), name


def test_no_reserved_word_is_used_as_a_function_name(
    gen: ModuleType, spec: Dict[str, Any]
) -> None:
    text = gen.generate(spec, SNAPSHOT.name)
    names = set(re.findall(r"^export async function (\w+)\(", text, re.M))
    assert not names & gen.RESERVED


def test_small_spec_shapes(gen: ModuleType) -> None:
    small = {
        "paths": {
            "/items/{item_id}": {
                "get": {
                    "operationId": "read_item_items__item_id__get",
                    "parameters": [
                        {
                            "in": "path",
                            "name": "item_id",
                            "required": True,
                            "schema": {"type": "string"},
                        },
                        {"in": "query", "name": "n", "schema": {"type": "integer"}},
                        {
                            "in": "header",
                            "name": "x-api-key",
                            "schema": {"type": "string"},
                        },
                    ],
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/Item"}
                                }
                            }
                        }
                    },
                },
                "delete": {
                    "operationId": "remove_items__item_id__delete",
                    "parameters": [
                        {
                            "in": "path",
                            "name": "item_id",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {"204": {}},
                },
            }
        },
        "components": {
            "schemas": {
                "Item": {
                    "type": "object",
                    "required": ["id"],
                    "properties": {
                        "id": {"type": "string"},
                        "tags": {"type": "array", "items": {"type": "string"}},
                        "kind": {"enum": ["a", "b"]},
                    },
                }
            }
        },
    }
    text = gen.generate(small, "small.json")
    assert (
        "export async function readItem(cfg: ClientConfig, args: { path: { item_id: string }; query?: { n?: number } })"
        in text
    )
    assert "Promise<Item>" in text
    assert (
        "export async function remove(cfg: ClientConfig, args: { path: { item_id: string } }): Promise<void>"
        in text
    )
    assert "encodeURIComponent(String(args.path.item_id))" in text
    assert "x-api-key" not in text.split("// ---- Operations")[1]
    assert 'kind?: "a" | "b";' in text


@pytest.mark.skipif(
    not (REPO / "frontend" / "node_modules" / ".bin").exists()
    or shutil.which("node") is None,
    reason="TypeScript compiler not installed",
)
def test_output_type_checks_with_tsc(
    gen: ModuleType, spec: Dict[str, Any], tmp_path: Path
) -> None:
    tsc = REPO / "frontend" / "node_modules" / "typescript" / "bin" / "tsc"
    if not tsc.exists():
        pytest.skip("tsc not found")
    target = tmp_path / "urbanflow.ts"
    target.write_text(gen.generate(spec, SNAPSHOT.name), encoding="utf-8", newline="\n")
    node = shutil.which("node")
    assert node is not None
    result = subprocess.run(
        [
            node,
            str(tsc),
            "--ignoreConfig",
            "--noEmit",
            "--strict",
            "--target",
            "es2022",
            "--lib",
            "es2022,dom",
            "--skipLibCheck",
            str(target),
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
