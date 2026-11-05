"""V2X messaging and cooperative-driving experiments (F19, package 2C).

Message schemas, a deterministic in-process bus (plus a lazy MQTT adapter),
a channel model (latency, loss, range), and a cooperative vs non-cooperative
experiment harness over ``src.networks``. Changes nothing in it."""

from src.v2x.bus import Envelope, InProcessBus, MessageBus
from src.v2x.channel import Channel, ChannelConfig
from src.v2x.experiment import run_experiment
from src.v2x.messages import (
    BasicSafetyMessage,
    HazardWarning,
    SignalPhaseAndTiming,
    parse_message,
    topic_for,
)

__all__ = [
    "BasicSafetyMessage",
    "Channel",
    "ChannelConfig",
    "Envelope",
    "HazardWarning",
    "InProcessBus",
    "MessageBus",
    "SignalPhaseAndTiming",
    "parse_message",
    "run_experiment",
    "topic_for",
]
