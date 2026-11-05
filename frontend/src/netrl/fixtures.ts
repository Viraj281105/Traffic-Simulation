/** Contract fixture for the network RL evaluation document: an RL policy
 *  against the fixed-time and max-pressure baselines over five held-out
 *  seeds. Not real results. */
import type { RlEvalDocument } from "./types";

const seeds = [10000, 10001, 10002, 10003, 10004];

export const evalFixture: RlEvalDocument = {
  format: "urbanflow-rl-eval",
  version: 1,
  kind: "network",
  seeds,
  env: { rows: 2, cols: 2, episode_seconds: 600 },
  signal_nodes: ["J1", "J2", "J3", "J4"],
  baseline_fixed_green_s: 30,
  metrics: ["mean_wait_s", "mean_queue", "throughput"],
  lower_is_better: ["mean_wait_s", "mean_queue"],
  policies: {
    fixed_time: {
      mean_wait_s: [41.2, 39.8, 43.5, 40.1, 42.6],
      mean_queue: [9.8, 9.4, 10.3, 9.6, 10.1],
      throughput: [212, 218, 205, 214, 209],
      wall_seconds: 3.2,
    },
    max_pressure: {
      mean_wait_s: [33.9, 32.7, 35.4, 33.1, 34.8],
      mean_queue: [8.1, 7.8, 8.6, 7.9, 8.4],
      throughput: [228, 231, 222, 229, 226],
      wall_seconds: 3.4,
    },
    rl_ppo: {
      mean_wait_s: [30.4, 31.9, 29.8, 33.6, 30.7],
      mean_queue: [7.4, 7.9, 7.1, 8.2, 7.5],
      throughput: [233, 229, 236, 224, 232],
      wall_seconds: 3.9,
    },
  },
  paired_comparisons: [
    {
      rl: "rl_ppo",
      baseline: "fixed_time",
      metric: "mean_wait_s",
      lower_is_better: true,
      comparison: {
        method: "paired_t",
        n_pairs: 5,
        mean_a: 31.28,
        mean_b: 41.44,
        difference: -10.16,
        ci_lower: -12.9,
        ci_upper: -7.42,
        confidence: 0.95,
        p_value: 0.0008,
        alpha: 0.05,
        significant: true,
        direction: "a_lower",
        statistic: -10.3,
        cautions: [],
      },
      verdict:
        "rl_ppo beats fixed_time: -10.16 (A minus B, 95% interval -12.9 to -7.42, p = 0.0008, paired_t, n = 5)",
    },
    {
      rl: "rl_ppo",
      baseline: "max_pressure",
      metric: "mean_wait_s",
      lower_is_better: true,
      comparison: {
        method: "paired_t",
        n_pairs: 5,
        mean_a: 31.28,
        mean_b: 33.98,
        difference: -2.7,
        ci_lower: -6.1,
        ci_upper: 0.7,
        confidence: 0.95,
        p_value: 0.098,
        alpha: 0.05,
        significant: false,
        direction: "none",
        statistic: -2.2,
        cautions: ["only 5 paired seeds: the interval is wide"],
      },
      verdict:
        "No reliable difference between rl_ppo and max_pressure: -2.7 (A minus B, 95% interval -6.1 to 0.7, p = 0.098, paired_t, n = 5)",
    },
    {
      rl: "rl_ppo",
      baseline: "fixed_time",
      metric: "mean_queue",
      lower_is_better: true,
      comparison: {
        method: "paired_t",
        n_pairs: 5,
        mean_a: 7.62,
        mean_b: 9.84,
        difference: -2.22,
        ci_lower: -2.9,
        ci_upper: -1.54,
        confidence: 0.95,
        p_value: 0.0021,
        alpha: 0.05,
        significant: true,
        direction: "a_lower",
        statistic: -8.1,
        cautions: [],
      },
      verdict:
        "rl_ppo beats fixed_time: -2.22 (A minus B, 95% interval -2.9 to -1.54, p = 0.0021, paired_t, n = 5)",
    },
  ],
  comparison_method: "paired_t",
  confidence: 0.95,
  cautions: [],
  environment: { python: "3.12.4", platform: "Linux-6.1" },
};
