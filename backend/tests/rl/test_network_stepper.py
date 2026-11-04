"""NetworkStepper reproduces simulate_network under the fixed schedule and honours phases."""

import pytest

from src.networks.network_sim import simulate_network
from src.rl.network_env import demo_network
from src.rl.network_stepper import NetworkStepper


def _run(stepper, steps, phases=None):
    for _ in range(steps):
        stepper.step(phases)
    return stepper.summary()


@pytest.mark.parametrize("seed", [1, 7])
def test_fixed_schedule_matches_simulate_network(seed):
    graph, flows = demo_network(2, 2)
    ref = simulate_network(graph, flows, duration=240.0, seed=seed)
    got = _run(NetworkStepper(graph, flows, seed=seed), 240)
    for key in (
        "generated",
        "entered",
        "blockedAtEntry",
        "completed",
        "active",
        "meanTravelSeconds",
        "meanDelaySeconds",
        "perLink",
        "perNode",
    ):
        assert got[key] == ref[key], key
    assert got["conserved"] is True


def test_controlled_run_is_deterministic_and_conserves():
    graph, flows = demo_network(2, 2)
    plan = {n: 1 for n in NetworkStepper(graph, flows).signal_nodes}
    a = _run(NetworkStepper(graph, flows, seed=3, clearance=2.0), 120, plan)
    b = _run(NetworkStepper(graph, flows, seed=3, clearance=2.0), 120, plan)
    assert a == b and a["conserved"]


def test_clearance_blocks_passing_and_counts_switch():
    graph, flows = demo_network(1, 1, vehicles_per_hour=900)
    st = NetworkStepper(graph, flows, seed=2, clearance=3.0)
    node = st.signal_nodes[0]
    for _ in range(40):
        st.step({node: 0})
    st.step({node: 1})
    assert st.in_transition(node) and st.switches[node] == 1
    passed = st.passed_node[node]
    st.step({node: 1})
    assert st.passed_node[node] == passed  # nothing passes during clearance
    for _ in range(3):
        st.step({node: 1})
    assert st.phase[node] == 1 and not st.in_transition(node)


def test_bad_phase_and_args_rejected():
    graph, flows = demo_network(1, 1)
    st = NetworkStepper(graph, flows)
    with pytest.raises(ValueError):
        st.step({st.signal_nodes[0]: 2})
    with pytest.raises(ValueError):
        NetworkStepper(graph, flows, dt=0)
