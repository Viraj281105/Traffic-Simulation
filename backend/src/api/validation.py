"""Configuration and scenario validation, translated into HTTP 400s.

The rules themselves belong to the domain: the shared JSON schema
(``core/schema.py``), the cross-field rules it cannot express
(``scenario/config_validation.py``) and the scenario-document checks
(``scenario/documents.py``). This module only decides how a failure reads to an
HTTP client, so every route that accepts an engine configuration or a
scenario document rejects it with the same message.
"""

from typing import Any, Dict, Optional

import jsonschema
from fastapi import HTTPException

from src.core.schema import CONFIG_SCHEMA
from src.scenario.config_validation import semantic_config_errors
from src.scenario.documents import parse_scenario, validate_scenario


def config_schema_error(config: Dict[str, Any]) -> Optional[str]:
    """The first schema violation in an engine configuration, or None."""
    try:
        jsonschema.validate(instance=config, schema=CONFIG_SCHEMA)
    except jsonschema.ValidationError as err:
        return str(err.message)
    return None


def check_engine_config_or_400(
    config: Dict[str, Any], semantic_source: Dict[str, Any]
) -> None:
    """Schema bounds on ``config``, then the contract's cross-field rules
    (docs/architecture/06-scenario-configuration-contract.md §5) on
    ``semantic_source`` — what the client actually sent, which for the typed
    route is not the defaults-filled dump (see semantic_config_errors)."""
    schema_error = config_schema_error(config)
    if schema_error is not None:
        raise HTTPException(
            status_code=400, detail=f"Invalid configuration: {schema_error}"
        )
    semantic_errors = semantic_config_errors(semantic_source)
    if semantic_errors:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid configuration: {'; '.join(semantic_errors)}",
        )


def valid_scenario_or_400(raw: Dict[str, Any], strategies: list[str]) -> Any:
    """The parsed scenario document, if it can run under every strategy."""
    result = validate_scenario(raw, strategies)
    if not result["valid"]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid scenario: {'; '.join(result['errors'])}",
        )
    document, _ = parse_scenario(raw)
    return document
