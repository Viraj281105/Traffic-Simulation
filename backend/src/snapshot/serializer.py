import json
from typing import Any, Dict


class Serializer:
    """Handles simulation state snapshot JSON serialization and validation."""

    @staticmethod
    def serialize(snapshot: Dict[str, Any]) -> str:
        """Serializes snapshot dictionary to a JSON string."""
        return json.dumps(snapshot)

    @staticmethod
    def deserialize(json_str: str) -> Dict[str, Any]:
        """Deserializes a JSON string to a snapshot dictionary."""
        from typing import cast
        return cast(Dict[str, Any], json.loads(json_str))
