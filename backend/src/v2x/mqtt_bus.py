"""MQTT adapter for :class:`~src.v2x.bus.MessageBus`.

Topics are ``urbanflow/v2x/<kind>/<node>``; payloads are the message's JSON
(wire names). ``paho-mqtt`` is NOT a pinned backend requirement: it is imported
lazily when an adapter is built without an injected client, so importing this
module never needs it. Real network delay and loss apply instead of the
channel model; ``Envelope.delivered_at`` is read from ``clock`` (default
``time.time``) and ``sent_at`` is the message's own timestamp, so the two are
only comparable when the publisher stamps wall-clock time.
"""

import importlib
import json
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from src.v2x.bus import AnyMessage, Envelope, Handler, Position
from src.v2x.messages import KINDS, parse_message, topic_for

_NO_PAHO = "paho-mqtt is not installed (pip install paho-mqtt)"


class MqttUnavailableError(RuntimeError):
    """paho-mqtt is not importable."""


def paho_available() -> bool:
    try:
        importlib.import_module("paho.mqtt.client")
    except ImportError:
        return False
    return True


def _default_client(client_id: str) -> Any:
    try:
        mqtt = importlib.import_module("paho.mqtt.client")
    except ImportError as err:
        raise MqttUnavailableError(_NO_PAHO) from err
    version = getattr(mqtt, "CallbackAPIVersion", None)
    if version is not None:  # paho-mqtt >= 2
        return mqtt.Client(version.VERSION2, client_id=client_id)
    return mqtt.Client(client_id=client_id)


class MqttBus:
    """Publishes and subscribes through an MQTT broker.

    ``client`` may be injected (any object with ``connect``, ``publish``,
    ``subscribe``, ``loop_start``, ``loop_stop``, ``disconnect`` and an
    assignable ``on_message``); tests use a fake, so no broker is needed.
    Nothing connects until :meth:`connect` is called."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 1883,
        client_id: str = "urbanflow-v2x",
        client: Optional[Any] = None,
        clock: Callable[[], float] = time.time,
        qos: int = 0,
    ) -> None:
        if not 0 <= qos <= 2:
            raise ValueError("qos must be 0, 1 or 2")
        self.host, self.port, self.qos = host, port, qos
        self._clock = clock
        self._client = client if client is not None else _default_client(client_id)
        self._handlers: List[Tuple[str, str, str, Handler]] = []
        self._client.on_message = self._on_message
        self.rejected = 0

    def connect(self, keepalive: int = 30) -> None:
        self._client.connect(self.host, self.port, keepalive)
        self._client.loop_start()

    def publish(
        self,
        kind: str,
        node: str,
        message: AnyMessage,
        *,
        now: float = 0.0,
        origin: Optional[Position] = None,
    ) -> None:
        topic = topic_for(kind, node)
        payload = message.model_dump_json(by_alias=True)
        self._client.publish(topic, payload, qos=self.qos)

    def subscribe(
        self,
        receiver: str,
        kind: str,
        node: str = "+",
        *,
        handler: Handler,
        position: Optional[Position] = None,
    ) -> None:
        topic = topic_for(kind, "x" if node == "+" else node)
        pattern = topic.rsplit("/", 1)[0] + "/" + node
        self._handlers.append((receiver, kind, node, handler))
        self._client.subscribe(pattern, qos=self.qos)

    def _on_message(self, _client: Any, _userdata: Any, msg: Any) -> None:
        topic: str = msg.topic
        parts = topic.split("/")
        if (
            len(parts) != 4
            or parts[:2] != ["urbanflow", "v2x"]
            or parts[2] not in KINDS
        ):
            self.rejected += 1
            return
        _, _, kind, node = parts
        try:
            body: Dict[str, Any] = json.loads(msg.payload)
            message = parse_message(body)
        except (ValueError, TypeError):
            self.rejected += 1  # malformed or out-of-range: dropped
            return
        if message.kind != kind:
            self.rejected += 1
            return
        received = self._clock()
        for receiver, k, n, handler in self._handlers:
            if k == kind and n in ("+", node):
                handler(Envelope(topic, message, message.timestamp, received, receiver))

    def close(self) -> None:
        self._client.loop_stop()
        self._client.disconnect()
