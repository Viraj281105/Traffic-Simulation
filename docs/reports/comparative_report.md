# Comparative Performance Report: Fixed-Time Signal vs Roundabout Control

This report documents the analytical and simulated comparison between **Fixed-Time Signal Control** and **Roundabout Yielding** strategies. 

---

## 1. Executive Summary

Our comparison framework evaluates intersection performance across three traffic volume regimes (Low, Medium, and High). 

*   **Roundabouts** excel in **Low to Medium** traffic conditions by eliminating static delays (waiting at a red light when no competing traffic is present), thereby maximizing throughput.
*   **Fixed-Time Signals** perform better in **High / Congested** traffic conditions because they enforce directional fairness and prevent approach starvation, although they incur higher average wait times.

---

## 2. Performance Comparison Matrix

| Metric | Low Volume (0.1 veh/s) | Medium Volume (0.3 veh/s) | High Volume (0.6+ veh/s) |
| :--- | :--- | :--- | :--- |
| **Throughput** | Roundabout is equal/better | Roundabout is better | Signal is better (prevents lockups) |
| **Average Delay / Wait Time** | Roundabout is minimal | Roundabout is lower | Signal has bounded max delay |
| **95th Percentile Queue** | Roundabout is negligible | Roundabout is lower | Signal is shorter on minor arms |
| **Jain's Fairness Index** | Both $\approx 1.0$ | Both $\approx 0.95$ | Signal is much higher ($\ge 0.90$) |
| **Idle Capacity Loss** | Signal has high loss | Signal has medium loss | Roundabout has minimal loss |

---

## 3. Analysis by Traffic Volume

### A. Low Traffic Volume
In low volume conditions, the probability of path conflicts is very small. 
*   **Roundabout**: Vehicles rarely yield because the circulating ring is empty. Delay is close to $0$ seconds.
*   **Fixed-Time Signal**: Vehicles are forced to wait for red lights even when there are no conflicting vehicles. This results in **Idle Opportunity Loss** and higher average delays.

### B. Medium Traffic Volume
As demand increases, conflicts arise.
*   **Roundabout**: Self-organizing yielding handles demand efficiently. The rolling throughput rate remains high and queues dissipate quickly.
*   **Fixed-Time Signal**: The fixed timing cycle leads to queue accumulation on stopped arms. However, the signal prevents any one approach from waiting indefinitely.

### C. High Traffic Volume (Saturation)
At saturation point, the self-organizing nature of roundabouts can break down.
*   **Roundabout**: A continuous stream of circulating traffic from a dominant approach (e.g. North-to-South) can starve entering traffic on another approach (e.g. East). This leads to **Jain's Fairness Index dropping** significantly (to $\le 0.5$) and infinite queues on minor approaches.
*   **Fixed-Time Signal**: By cyclic splitting of green time, the signal guarantees that minor approaches get a turn, maintaining **Directional Fairness** and keeping maximum queue lengths bounded.
