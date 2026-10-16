"""State for the single-vehicle polling mode (Sprint 2 UI compatibility).

One scripted vehicle, advanced by each GET of /api/simulation/single-vehicle
while running. It is not a simulation: no engine, physics or metrics.
"""


class SingleVehicleState:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.vehicle_id = "vehicle_1"
        self.position = 0.0
        self.speed = 10.0
        self.acceleration = 0.0
        self.x = -150.0
        self.y = -3.5
        self.heading = 90.0
        self.state = "approaching"
        self.lane_id = "w_in_0"
        self.wait_time = 0.0
        self.stop_count = 0
        self.sim_time = 0.0
        self.tick = 0
        self.status = "stopped"


single_veh = SingleVehicleState()
