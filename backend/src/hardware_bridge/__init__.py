"""Hardware bridge (F19, package 3E): simulated signal plan -> head commands
over a message bus -> a pure-Python device simulator with an on-device safety
interlock. SIMULATION ONLY: nothing here contacts real hardware or a broker
unless the caller explicitly wires an ``MqttHwBus`` to one."""
