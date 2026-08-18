import json
from typing import Any, Dict, List, Optional


class SnapshotBuffer:
    """Manages a rolling history cache of simulation state snapshots."""

    def __init__(self, max_frames: int = 1000) -> None:
        self.max_frames: int = max_frames
        self.buffer: List[Dict[str, Any]] = []

    def append(self, snapshot: Dict[str, Any]) -> None:
        """Appends a new snapshot frame. Truncates older frames if capacity is reached."""
        self.buffer.append(snapshot)
        if len(self.buffer) > self.max_frames:
            self.buffer.pop(0)

    def get_frame(self, tick: int) -> Optional[Dict[str, Any]]:
        """Retrieves a specific snapshot frame corresponding to the tick count."""
        for frame in self.buffer:
            if frame.get("tick") == tick:
                return frame
        return None

    def clear(self) -> None:
        """Clears the buffer cache."""
        self.buffer.clear()

    def get_all(self) -> List[Dict[str, Any]]:
        """Returns all cached frames."""
        return self.buffer

    def export_to_file(self, filepath: str) -> None:
        """Saves the entire run history as a single JSON file."""
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.buffer, f, indent=2)
