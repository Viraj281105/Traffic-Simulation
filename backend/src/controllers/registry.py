from typing import Any, Dict, Type

from src.controllers.base import BaseController


class ControllerRegistry:
    """Centralized registry for mapping and instantiating traffic controllers by their type/name."""

    _registry: Dict[str, Type[BaseController]] = {}

    @classmethod
    def register(cls, name: str) -> Any:
        """Decorator to register a controller class under a specific string name."""

        def decorator(subclass: Type[BaseController]) -> Type[BaseController]:
            cls._registry[name] = subclass
            return subclass

        return decorator

    @classmethod
    def get_controller_class(cls, name: str) -> Type[BaseController]:
        """Retrieves the controller class registered under the given name."""
        if name not in cls._registry:
            raise KeyError(f"Controller type '{name}' is not registered.")
        return cls._registry[name]


# Import and register the controllers to ensure they are registered when registry is imported
from src.controllers.fixed_time_signal import FixedTimeSignalController
from src.controllers.roundabout import RoundaboutController

ControllerRegistry._registry["fixed_time_signal"] = FixedTimeSignalController
ControllerRegistry._registry["roundabout"] = RoundaboutController
