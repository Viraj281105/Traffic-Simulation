import logging
import math
import random
from collections import deque
from typing import Any, Deque, Dict, List, NamedTuple, Optional, Set

from src.core.enums import Direction, TurnIntent
from src.core.limits import DEFAULT_TOTAL_VEHICLES
from src.core.speed_thresholds import resolve_speed_threshold
from src.roads.lane import Lane
from src.roads.network import RoadNetwork
from src.vehicles.driver_aggression import (
    aggression_multipliers_for,
    apply_aggression_to_speed_range,
    resolve_aggression_name,
)
from src.vehicles.speed_profile import resolve_desired_speed_range
from src.vehicles.variability import (
    DemandFactors,
    DriverDraws,
    parse_demand_variability,
    parse_driver_heterogeneity,
)
from src.vehicles.vehicle import Vehicle
from src.vehicles.vehicle_types import (
    VehicleParams,
    VehiclePopulation,
    approach_vehicle_mixes,
    resolve_vehicle_population,
)

logger = logging.getLogger(__name__)


class _QueuedArrival(NamedTuple):
    """An arrival waiting in the entry queue (traffic.entryQueue)."""

    arrival_time: float
    turn: TurnIntent
    type_id: Optional[str]


class VehicleSpawner:
    """Spawns vehicles onto the road network using arrival processes (Poisson or Uniform).

    Lane assignment is turn-intent-aware:
        - 1 lane:  all turns share the lane.
        - 2 lanes: lane 0 = left-turn, lane 1 = straight/right.
        - 3+ lanes: lane 0 = left, middle = straight, last = right.
    """

    def __init__(self, config: Dict[str, Any], network: RoadNetwork) -> None:
        self.config: Dict[str, Any] = config
        self.network: RoadNetwork = network

        traffic_cfg = config.get("traffic", {})
        # setdefault (not get) so that if we generate a fallback seed below,
        # writing it into sim_cfg is visible to every other holder of this
        # same config dict (engine, API handlers, persistence/reproduction
        # code) via config["simulation"]["randomSeed"].
        sim_cfg = config.setdefault("simulation", {})
        veh_gen_cfg = config.get("vehicleGeneration", {})

        self.random_seed: int = sim_cfg.get("randomSeed", veh_gen_cfg.get("seed", None))
        if self.random_seed is None:
            # Never fall back to the shared global `random` module — its
            # state is process-wide and can be perturbed by unrelated code
            # (including other concurrent simulations), which is exactly
            # the kind of silent, hidden non-determinism a "randomSeed"
            # config knob is meant to avoid. Use a private, independently
            # OS-seeded Random instance instead, purely to pick this
            # simulation's own seed.
            self.random_seed = random.Random().randint(1, 10_000_000)
            logger.warning(
                "No simulation.randomSeed configured; generated seed=%d "
                "for this run. Pass randomSeed explicitly for reproducible "
                "runs.",
                self.random_seed,
            )
            # Persist the resolved seed back into the shared config so it
            # can be captured/logged/persisted by callers (e.g. the run
            # history and reproduce endpoints in history/router.py).
            sim_cfg["randomSeed"] = self.random_seed
        self.rng: random.Random = random.Random(self.random_seed)

        # Opt-in variability (ADR-020), each on its own stream so enabling it
        # cannot shift any draw above or below. None = off = bit-identical.
        self._driver_model = parse_driver_heterogeneity(traffic_cfg)
        self._demand_model = parse_demand_variability(traffic_cfg)
        self._driver_draws: Optional[DriverDraws] = None
        self._demand_factors: Optional[DemandFactors] = None

        self.total_vehicles_limit: int = traffic_cfg.get(
            "totalVehicles", DEFAULT_TOTAL_VEHICLES
        )
        self.arrival_rate: float = traffic_cfg.get(
            "arrivalRate", veh_gen_cfg.get("arrivalRate", 0.5)
        )
        self.arrival_distribution: str = traffic_cfg.get(
            "arrivalDistribution", "poisson"
        )

        if (
            "directionalSplit" in traffic_cfg
            and traffic_cfg["directionalSplit"] is not None
        ):
            self.directional_split: Dict[str, float] = traffic_cfg["directionalSplit"]
        else:
            # Generate stochastic non-uniform weights for the 4 approaches
            raw_weights = [self.rng.uniform(0.5, 2.0) for _ in Direction]
            total_w = sum(raw_weights)
            self.directional_split = {
                d.value: raw_weights[i] / total_w for i, d in enumerate(Direction)
            }

        if (
            "turnProbabilities" in traffic_cfg
            and traffic_cfg["turnProbabilities"] is not None
        ):
            self.turn_probabilities: Dict[str, float] = traffic_cfg["turnProbabilities"]
        else:
            # Realistic randomized turn probabilities with natural variance per run
            p_straight = self.rng.uniform(0.50, 0.70)
            rem = 1.0 - p_straight
            p_left = self.rng.uniform(0.3, 0.7) * rem
            p_right = rem - p_left
            self.turn_probabilities = {
                "left": p_left,
                "straight": p_straight,
                "right": p_right,
            }

        # Vehicle physical parameter bounds
        self.len_min: float = veh_gen_cfg.get("vehicleLength", {}).get("min", 4.0)
        self.len_max: float = veh_gen_cfg.get("vehicleLength", {}).get("max", 5.0)
        self.width_min: float = veh_gen_cfg.get("vehicleWidth", {}).get("min", 1.8)
        self.width_max: float = veh_gen_cfg.get("vehicleWidth", {}).get("max", 2.2)
        # Desired speed: explicit vehicleGeneration.desiredSpeed, otherwise
        # derived from roads.speedLimit (see speed_profile.py). It used to
        # default to 18-25 m/s whatever the speed limit said.
        # The legacy cars-only population takes the driver-aggression speed
        # offset here; a mixed one takes it per class (resolve_vehicle_population).
        self.speed_min, self.speed_max = apply_aggression_to_speed_range(
            resolve_desired_speed_range(config), resolve_aggression_name(config)
        )

        # Safety distance
        m = aggression_multipliers_for(config)
        self.minimum_gap: float = (
            float(veh_gen_cfg.get("minimumGap", 2.0)) * m["gap_mult"]
        )
        # Deceleration a newly inserted vehicle is assumed to be able to use
        # to stop behind the vehicle it is inserted behind (see
        # _safe_insertion_speed). Same parameter, and same default, as the
        # IDM's own comfortable deceleration (SimulationEngine.__init__).
        self.comfort_deceleration: float = veh_gen_cfg.get("comfortDeceleration", 3.0)

        # Mixed vehicle classes (V1.1), or None for the legacy single-car
        # population, which is then drawn exactly as in V1.0 (same random
        # stream), so existing scenarios reproduce unchanged.
        self.population: Optional[VehiclePopulation] = resolve_vehicle_population(
            config
        )
        # V1.4: approaches with their own composition and turning.
        self.approach_populations: Dict[str, VehiclePopulation] = {}
        for direction, mix in approach_vehicle_mixes(config).items():
            own = resolve_vehicle_population(config, mix)
            if own is not None:
                self.approach_populations[direction] = own
        self.approach_turn_probabilities: Dict[str, Dict[str, float]] = {}
        for item in traffic_cfg.get("approaches") or []:
            if isinstance(item, dict) and isinstance(
                item.get("turnProbabilities"), dict
            ):
                self.approach_turn_probabilities[
                    str(item.get("direction", "")).lower()
                ] = item["turnProbabilities"]

        # Speed below which a vehicle is considered "waiting" — must match
        # MetricCollector's wait_speed_threshold so wait-time accounting is
        # consistent between the vehicle and the metrics layer.
        self.wait_speed_threshold: float = resolve_speed_threshold(
            config, "waitSpeedThreshold", 0.5
        )

        # Vehicles spawned count
        self.spawned_count: int = 0

        # Cumulative simulation time — used to set vehicle spawn_time
        self._elapsed_time: float = 0.0

        # Spawn timers for each direction
        self.timers: Dict[Direction, float] = {}
        # Turn intent of an arrival that is due but could not be placed yet
        # (its entry lane was blocked). It keeps that intent until it is
        # actually placed — see _attempt_spawn.
        self._pending_turn: Dict[Direction, TurnIntent] = {}
        # Vehicle class of that same pending arrival (mixed populations only):
        # like its turn, a property of the arriving vehicle, drawn once.
        self._pending_type: Dict[Direction, str] = {}

        # Demand accounting (see demand_accounting()). Counters only: they
        # draw nothing from self.rng and never touch the timers, so a run
        # reproduces exactly as it did before they existed.
        self._arrivals: Dict[Direction, int] = {}
        self._admitted: Dict[Direction, int] = {}
        self._blocked_seconds: Dict[Direction, float] = {}
        # Approaches holding an arrival that is due but not yet placed.
        self._held: Set[Direction] = set()
        # Time during which the source generated arrivals (it stops once
        # totalVehicles is reached).
        self._generation_time: float = 0.0
        # When each approach's held arrival became due (suspend model), and
        # the entry waits of admitted vehicles, for both entry models.
        self._due_time: Dict[Direction, float] = {}
        self._entry_wait_sum: float = 0.0
        self._entry_wait_max: float = 0.0

        # Entry model (traffic.entryQueue). Default "suspend": a full entry
        # holds one arrival and suspends that approach's arrival process (see
        # step()). Opt-in "queue": the arrival process keeps running and
        # arrivals that cannot enter wait in a first-in-first-out point queue
        # outside the network (a vertical queue: it occupies no road), so all
        # demand is generated and either admitted later, still waiting, or,
        # beyond an optional per-approach capacity, rejected.
        entry_queue = traffic_cfg.get("entryQueue") or {}
        self.entry_queue: bool = bool(entry_queue.get("enabled", False))
        capacity = entry_queue.get("capacity")
        self.entry_queue_capacity: Optional[int] = (
            int(capacity) if capacity is not None else None
        )
        self._backlog: Dict[Direction, Deque[_QueuedArrival]] = {}
        self._rejected: Dict[Direction, int] = {}
        self.reset()

    def reset(self, new_seed: Optional[int] = None) -> None:
        if new_seed is not None:
            self.random_seed = new_seed
        # Re-seed in place rather than replacing the generator: the stochastic
        # IDM shares this object (SimulationEngine passes it in), and a new one
        # left it drawing from the previous run's stream, so a reset run with
        # unstructuredTraffic did not reproduce a fresh one. seed() puts the
        # generator in exactly the state random.Random(seed) starts in.
        self.rng.seed(self.random_seed)
        self._driver_draws = (
            DriverDraws(self._driver_model, self.random_seed)
            if self._driver_model is not None
            else None
        )
        self._demand_factors = (
            DemandFactors(self._demand_model, self.random_seed)
            if self._demand_model is not None
            else None
        )
        self.spawned_count = 0
        self._elapsed_time = 0.0
        self.timers.clear()
        self._pending_turn.clear()
        self._pending_type.clear()
        self._arrivals = {d: 0 for d in Direction}
        self._admitted = {d: 0 for d in Direction}
        self._blocked_seconds = {d: 0.0 for d in Direction}
        self._held.clear()
        self._generation_time = 0.0
        self._due_time.clear()
        self._entry_wait_sum = 0.0
        self._entry_wait_max = 0.0
        self._backlog = {d: deque() for d in Direction}
        self._rejected = {d: 0 for d in Direction}

        traffic_cfg = self.config.get("traffic", {})
        if (
            "directionalSplit" not in traffic_cfg
            or traffic_cfg.get("directionalSplit") is None
        ):
            raw_weights = [self.rng.uniform(0.5, 2.0) for _ in Direction]
            total_w = sum(raw_weights)
            self.directional_split = {
                d.value: raw_weights[i] / total_w for i, d in enumerate(Direction)
            }
        if (
            "turnProbabilities" not in traffic_cfg
            or traffic_cfg.get("turnProbabilities") is None
        ):
            p_straight = self.rng.uniform(0.50, 0.70)
            rem = 1.0 - p_straight
            p_left = self.rng.uniform(0.3, 0.7) * rem
            p_right = rem - p_left
            self.turn_probabilities = {
                "left": p_left,
                "straight": p_straight,
                "right": p_right,
            }

        for d in Direction:
            self.timers[d] = self._generate_next_arrival_time(d)

    def _generate_next_arrival_time(self, direction: Direction) -> float:
        split = self.directional_split.get(direction.value, 0.25)
        dir_rate = self.arrival_rate * split
        if self._demand_factors is not None:
            dir_rate *= self._demand_factors.factor_at(self._elapsed_time)
        if dir_rate <= 0:
            return float("inf")

        if self.arrival_distribution == "poisson":
            u = self.rng.random()
            # Prevent log(0)
            u = max(1e-9, u)
            return -math.log(u) / dir_rate
        if self.arrival_distribution == "uniform":
            return 1.0 / dir_rate
        if self.arrival_distribution == "burst":
            raise NotImplementedError(
                "arrivalDistribution='burst' is not implemented in VehicleSpawner"
            )
        raise ValueError(
            f"Unsupported arrivalDistribution: {self.arrival_distribution!r}"
        )

    def step(self, dt: float) -> List[Vehicle]:
        """Ticks spawner and returns a list of newly spawned vehicles."""
        self._elapsed_time += dt
        if self.entry_queue:
            return self._step_queued(dt)
        new_vehicles: List[Vehicle] = []

        # Check total vehicle limit
        if self.spawned_count >= self.total_vehicles_limit:
            return new_vehicles
        self._generation_time += dt

        for d in Direction:
            if self.timers[d] != float("inf"):
                self.timers[d] -= dt
                if self.timers[d] <= 0:
                    if d not in self._held:
                        self._arrivals[d] += 1
                        self._due_time[d] = self._elapsed_time
                    # Attempt spawning
                    vehicle = self._attempt_spawn(d)
                    if vehicle is not None:
                        new_vehicles.append(vehicle)
                        self.spawned_count += 1
                        self._admitted[d] += 1
                        self._held.discard(d)
                        self._record_entry_wait(
                            vehicle, self._elapsed_time - self._due_time.pop(d)
                        )
                        self.timers[d] = self._generate_next_arrival_time(d)
                        if self.spawned_count >= self.total_vehicles_limit:
                            break
                    else:
                        # If blocked, try again next tick. The arrival process
                        # on this approach is suspended meanwhile: the next
                        # arrival is only drawn once this one is placed, so
                        # no further demand is generated here until then.
                        self.timers[d] = 0.0
                        self._held.add(d)
                        self._blocked_seconds[d] += dt

        return new_vehicles

    def _step_queued(self, dt: float) -> List[Vehicle]:
        """One tick of the opt-in point-queue entry model.

        Per approach: the arrival clock runs whether or not the entry is
        full; a due arrival draws its turn and class (properties of the
        arriving driver, as in the suspend model) and joins the back of the
        approach's queue, or is rejected when the queue is at capacity. Then
        the head of the queue is offered the entry, at most one vehicle per
        approach per tick, exactly as a held arrival is in the suspend model.
        Generation stops once ``totalVehicles`` arrivals have been generated;
        those already queued are still admitted as space allows.

        The arrival clock is exact: each inter-arrival time is added to the
        time left over when the previous arrival fell due (not restarted at
        the tick boundary), every arrival due within the tick is generated,
        and each records the moment it fell due. Restarting the clock lost
        about half a tick per arrival, so the queue model generated fewer
        arrivals than configured (about 1 % at 900 veh/h per arm, about 11 %
        at the maximum rate) and timed entry waits from the tick's end. The
        default "suspend" model keeps its restart, so its results, and every
        golden pin, reproduce (F-57).
        """
        new_vehicles: List[Vehicle] = []
        if self._total_arrivals() < self.total_vehicles_limit:
            self._generation_time += dt
        for d in Direction:
            if self.timers[d] == float("inf"):
                continue
            backlog = self._backlog[d]
            if self._total_arrivals() < self.total_vehicles_limit:
                self.timers[d] -= dt
                while (
                    self.timers[d] <= 0
                    and self._total_arrivals() < self.total_vehicles_limit
                ):
                    # timers[d] <= 0 is how long ago, within this tick, the
                    # arrival fell due.
                    due = self._elapsed_time + self.timers[d]
                    self._arrivals[d] += 1
                    if (
                        self.entry_queue_capacity is not None
                        and len(backlog) >= self.entry_queue_capacity
                    ):
                        self._rejected[d] += 1
                    else:
                        turn = self._draw_turn(d)
                        population = self.approach_populations.get(
                            d.value, self.population
                        )
                        type_id = (
                            self._draw_type(population)
                            if population is not None
                            else None
                        )
                        backlog.append(_QueuedArrival(due, turn, type_id))
                    self.timers[d] += self._generate_next_arrival_time(d)
            if not backlog:
                continue
            head = backlog[0]
            self._pending_turn[d] = head.turn
            if head.type_id is not None:
                self._pending_type[d] = head.type_id
            vehicle = self._attempt_spawn(d)
            if vehicle is None:
                self._blocked_seconds[d] += dt
                continue
            backlog.popleft()
            new_vehicles.append(vehicle)
            self.spawned_count += 1
            self._admitted[d] += 1
            self._record_entry_wait(vehicle, self._elapsed_time - head.arrival_time)
        return new_vehicles

    def _total_arrivals(self) -> int:
        return sum(self._arrivals.values())

    def _record_entry_wait(self, vehicle: Vehicle, wait: float) -> None:
        vehicle.entry_wait = wait
        self._entry_wait_sum += wait
        if wait > self._entry_wait_max:
            self._entry_wait_max = wait

    def _waiting(self, d: Direction) -> int:
        if self.entry_queue:
            return len(self._backlog[d])
        return 1 if d in self._held else 0

    def demand_accounting(self) -> Dict[str, Any]:
        """Offered, admitted and waiting demand since the start of the run.

        Exact counts: ``arrivals`` is every arrival the source generated,
        ``admitted`` those placed on an entry lane (``totalVehiclesSpawned``),
        ``waitingAtEntry`` those generated but not yet placed because every
        permitted entry lane was full, and ``rejected`` those turned away by
        a full entry queue, so ``arrivals == admitted + waitingAtEntry +
        rejected`` always holds. ``entryBlockedSeconds`` is the time
        approaches spent with an arrival unable to enter; the entry-wait
        figures describe admitted vehicles (time from arrival to entry) and
        the oldest arrival still waiting.

        ``entryModel`` says how a full entry is handled. ``"suspend"``
        (default): one arrival waits per approach and that approach's
        arrival process is suspended (see step()), so demand that would
        have arrived meanwhile is never generated, and ``rejected`` is 0.
        ``"queue"`` (``traffic.entryQueue``): arrivals keep coming and wait in
        a point queue outside the network (see _step_queued).

        ``nominalDemand`` (configured rate x the time the source ran) and
        ``estimatedSuppressedArrivals`` (rate x blocked time under the
        suspend model, the expected number the suspended process did not
        generate; 0 under the queue model, whose arrival clock never stops)
        are expectations from the configuration, not counts, and
        ``demandFiguresAreEstimates`` says so. Whole run from t = 0, like
        ``totalVehiclesSpawned``; arms with no demand are omitted.
        """
        by_approach: Dict[str, Dict[str, Any]] = {}
        nominal_total = 0.0
        suppressed_total = 0.0
        for d in Direction:
            rate = self.arrival_rate * self.directional_split.get(d.value, 0.25)
            if rate <= 0 or self.timers.get(d) == float("inf"):
                continue
            nominal = rate * self._generation_time
            suppressed = 0.0 if self.entry_queue else rate * self._blocked_seconds[d]
            nominal_total += nominal
            suppressed_total += suppressed
            by_approach[d.value] = {
                "arrivals": self._arrivals[d],
                "admitted": self._admitted[d],
                "waitingAtEntry": self._waiting(d),
                "rejected": self._rejected[d],
                "entryBlockedSeconds": round(self._blocked_seconds[d], 2),
                "nominalDemand": round(nominal, 2),
                "estimatedSuppressedArrivals": round(suppressed, 2),
            }
        admitted = sum(self._admitted.values())
        if self.entry_queue:
            oldest = min(
                (q[0].arrival_time for q in self._backlog.values() if q),
                default=None,
            )
        else:
            oldest = min(self._due_time.values(), default=None)
        return {
            "entryModel": "queue" if self.entry_queue else "suspend",
            "arrivals": self._total_arrivals(),
            "admitted": admitted,
            "waitingAtEntry": sum(self._waiting(d) for d in Direction),
            "rejected": sum(self._rejected.values()),
            "entryBlockedSeconds": round(sum(self._blocked_seconds.values()), 2),
            "meanEntryWaitSeconds": (
                round(self._entry_wait_sum / admitted, 2) if admitted else None
            ),
            "maxEntryWaitSeconds": round(self._entry_wait_max, 2),
            "oldestWaitingSeconds": (
                round(self._elapsed_time - oldest, 2) if oldest is not None else None
            ),
            "nominalDemand": round(nominal_total, 2),
            "estimatedSuppressedArrivals": round(suppressed_total, 2),
            "admittedShareOfNominal": (
                round(admitted / nominal_total, 4) if nominal_total > 0 else None
            ),
            "demandFiguresAreEstimates": True,
            "byApproach": by_approach,
        }

    def _select_lane_for_turn(self, lanes: List[Lane], turn: TurnIntent) -> int:
        """Return the best lane index for the given turn intent.

        Policy (right-hand traffic):
            1 lane  → lane 0 for everything.
            2 lanes → lane 0 = left, lane 1 = straight / right.
            3+ lanes → lane 0 = left, middle lanes = straight, last = right.
        """
        n = len(lanes)
        if n <= 1:
            return 0

        # A U-turn (V1.5) starts, like a left turn, from the left-most lane.
        if n == 2:
            if turn in (TurnIntent.LEFT, TurnIntent.UTURN):
                return 0
            return 1  # straight or right

        # 3+ lanes
        if turn in (TurnIntent.LEFT, TurnIntent.UTURN):
            return 0
        elif turn == TurnIntent.RIGHT:
            return n - 1
        else:
            # Straight → pick a middle lane
            return n // 2

    def _draw_turn(self, direction: Direction) -> TurnIntent:
        """One arriving driver's turn intent (one draw from self.rng)."""
        turns = [TurnIntent.LEFT, TurnIntent.STRAIGHT, TurnIntent.RIGHT]
        probabilities = self.approach_turn_probabilities.get(
            direction.value, self.turn_probabilities
        )
        weights = [
            probabilities.get("left", 0.2),
            probabilities.get("straight", 0.6),
            probabilities.get("right", 0.2),
        ]
        # V1.5: a U-turn share joins the draw only where an approach has
        # one, so every earlier scenario draws exactly as before.
        uturn = probabilities.get("uturn") or 0.0
        if uturn > 0:
            turns.append(TurnIntent.UTURN)
            weights.append(uturn)
        return self.rng.choices(turns, weights=weights)[0]

    def _draw_type(self, population: VehiclePopulation) -> str:
        """One arriving vehicle's class (one draw from self.rng)."""
        return self.rng.choices(population.type_ids, weights=population.weights)[0]

    def _attempt_spawn(self, direction: Direction) -> Optional[Vehicle]:
        incoming_approach = self.network.get_incoming_approach(direction)
        lanes = incoming_approach.get_lanes()
        if not lanes:
            return None

        # Decide Turn Intent first (so we can pick the correct lane).
        #
        # An arrival whose lane is blocked is retried every tick. It used to
        # draw a brand-new turn intent on each retry, so a blocked left- or
        # right-turner (confined to one lane) was simply re-rolled until it
        # drew "straight" (which may use any lane) and got in. Under
        # congestion that rewrote the configured turning mix — at 1.5 veh/s on
        # two lanes, 30/40/30 left/straight/right came out as 28/46/25. The
        # intent is a property of the arriving driver, so it is drawn once and
        # kept until that vehicle is actually placed.
        turn = self._pending_turn.get(direction)
        if turn is None:
            turn = self._draw_turn(direction)
            self._pending_turn[direction] = turn

        # Vehicle class, drawn once per arrival and kept while it waits for
        # space, for the same reason as the turn above: a blocked bus must
        # not be re-rolled into a car until it fits. A longer class needs a
        # longer free entry, so the clearance test below uses its own length.
        params: Optional[VehicleParams] = None
        population = self.approach_populations.get(direction.value, self.population)
        if population is not None:
            type_id = self._pending_type.get(direction)
            if type_id is None:
                type_id = self._draw_type(population)
                self._pending_type[direction] = type_id
            params = population.params_by_type[type_id]
            required_length = params.profile.max_length
            minimum_gap = params.minimum_gap
        else:
            required_length = self.len_max
            minimum_gap = self.minimum_gap

        # Select the preferred lane for this turn intent
        preferred_idx = self._select_lane_for_turn(lanes, turn)

        # Try the preferred lane first, then any other lane the movement is
        # permitted from (RoadNetwork's lane-use policy): turning vehicles
        # therefore only ever enter their own turn lane, through traffic any.
        #
        # V1.4: with a configured lane use the policy's preferred lane may not
        # permit the movement at all (a scenario that makes lane 0 a
        # straight-only lane), so it is only tried first when it does. Under
        # the default policy it always does, and the order is unchanged.
        n_lanes = len(lanes)
        permitted = [
            i
            for i in range(n_lanes)
            if turn in self.network.permitted_turns(direction, i)
        ]
        if permitted and preferred_idx not in permitted:
            preferred_idx = min(permitted, key=lambda i: (abs(i - preferred_idx), i))
        ordered_indices = [preferred_idx] + [i for i in permitted if i != preferred_idx]

        target_lane: Optional[Lane] = None
        target_idx: int = preferred_idx
        target_preceding: Optional[Vehicle] = None

        for idx in ordered_indices:
            lane = lanes[idx]
            vehicles = lane.get_vehicles()
            if not vehicles:
                target_lane = lane
                target_idx = idx
                break
            # Find vehicle with the minimum position in the lane
            preceding = min(vehicles, key=lambda v: v.position)
            # Tail of preceding vehicle: preceding.position - preceding.length / 2
            # We need it to be >= minimum_gap + new_vehicle_length
            if (
                preceding.position - preceding.length / 2.0
                >= minimum_gap + required_length
            ):
                target_lane = lane
                target_idx = idx
                target_preceding = preceding
                break

        if target_lane is None:
            return None
        del self._pending_turn[direction]
        self._pending_type.pop(direction, None)

        # Generate vehicle parameters
        if params is None:
            v_len = self.rng.uniform(self.len_min, self.len_max)
            v_width = self.rng.uniform(self.width_min, self.width_max)
            v_desired_speed = self.rng.uniform(self.speed_min, self.speed_max)
            insertion_decel = self.comfort_deceleration
        else:
            profile = params.profile
            v_len = self.rng.uniform(*profile.length)
            v_width = self.rng.uniform(*profile.width)
            v_desired_speed = self.rng.uniform(*params.desired_speed_range)
            insertion_decel = profile.comfort_deceleration

        initial_speed = v_desired_speed
        if target_preceding is not None:
            initial_speed = min(
                initial_speed,
                self._safe_insertion_speed(
                    target_preceding, v_len, insertion_decel, minimum_gap
                ),
            )

        # Generate Route using the selected lane index and turn intent
        route = self.network.generate_route(direction, target_idx, turn)

        # Create Vehicle
        vehicle_id = f"veh_{self.spawned_count}"

        # Vehicle starts at position L/2 so that its rear bumper is at 0.0
        start_pos = v_len / 2.0

        vehicle = Vehicle(
            vehicle_id=vehicle_id,
            length=v_len,
            width=v_width,
            desired_speed=v_desired_speed,
            route=route,
            start_position=start_pos,
            initial_speed=initial_speed,
            turn_intent=turn,
            spawn_time=self._elapsed_time,
            wait_speed_threshold=self.wait_speed_threshold,
            params=params,
        )
        if self._driver_draws is not None:
            vehicle.driver_factors = self._driver_draws.next_factors()

        return vehicle

    def _safe_insertion_speed(
        self,
        preceding: Vehicle,
        new_length: float,
        comfort_deceleration: Optional[float] = None,
        minimum_gap: Optional[float] = None,
    ) -> float:
        """Highest speed at which a vehicle inserted behind *preceding* can stop.

        A vehicle used to be inserted at its full desired speed (up to
        25 m/s) whenever the entry had a few metres of clearance, however slow
        the vehicle just ahead was. Behind a queue that had grown back towards
        the entry, that is a car arriving at motorway speed with 3 m to spare:
        even braking at the IDM's hard limit it cannot stop, and it drove
        straight into — and through — the car in front. Being on the same lane,
        that overlap was never even counted as a collision.

        The insertion speed is capped so that, braking at the comfortable
        deceleration, the new vehicle stops no closer than ``minimumGap``
        behind where the preceding vehicle would stop braking the same way
        (the usual safe-speed condition, v^2/2b <= s + v_l^2/2b). On an empty
        entry or behind a free-flowing leader the cap is above the desired
        speed and has no effect.

        ``comfort_deceleration`` and ``minimum_gap`` are the new vehicle's own
        (its class's) values; they default to the scenario-wide ones.
        """
        decel = (
            self.comfort_deceleration
            if comfort_deceleration is None
            else comfort_deceleration
        )
        s0 = self.minimum_gap if minimum_gap is None else minimum_gap
        # The new vehicle's front bumper will be at new_length (it is placed
        # with its rear bumper on the lane start — see _attempt_spawn).
        gap = preceding.position - preceding.length / 2.0 - new_length
        usable = max(0.0, gap - s0)
        return math.sqrt(preceding.speed * preceding.speed + 2.0 * decel * usable)
