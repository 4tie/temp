from __future__ import annotations

import unittest

from app.ai.evolution.evolver import _evaluate_regime_robustness
from app.ai.evolution.fitness import compute_fitness


class FitnessTests(unittest.TestCase):
    def test_compute_fitness_returns_zero_for_insufficient_trades(self) -> None:
        result = {
            "summary": {
                "profitFactor": 2.0,
                "sharpeRatio": 1.5,
                "maxDrawdown": 10.0,
                "winRate": 60.0,
            },
            "advanced_metrics": {"sharpe_ratio": 1.5},
            "trades": [{"profit": 1.0}] * 19,
        }

        fitness = compute_fitness(result)

        self.assertEqual(fitness.value, 0.0)
        self.assertEqual(fitness.breakdown["reason"], "insufficient_trades")

    def test_compute_fitness_uses_requested_formula_and_caps_total(self) -> None:
        result = {
            "summary": {
                "profitFactor": 1.5,
                "sharpeRatio": 1.2,
                "maxDrawdown": 10.0,
                "winRate": 55.0,
            },
            "advanced_metrics": {"sharpe_ratio": 1.2},
            "trades": [{"profit": 1.0}] * 100,
        }

        fitness = compute_fitness(result)

        self.assertAlmostEqual(fitness.breakdown["profit_factor_score"], 15.0, places=2)
        self.assertAlmostEqual(fitness.breakdown["sharpe_score"], 9.0, places=2)
        self.assertAlmostEqual(fitness.breakdown["drawdown_score"], 20.0, places=2)
        self.assertAlmostEqual(fitness.breakdown["win_rate_score"], 11.0, places=2)
        self.assertAlmostEqual(fitness.breakdown["trade_bonus_score"], 10.0, places=2)
        self.assertAlmostEqual(fitness.value, 65.0, places=2)

    def test_regime_robustness_requires_weakest_regime_not_to_worsen(self) -> None:
        base = {
            "regime_analysis": {
                "per_regime_performance": {
                    "trending": {"trade_count": 15, "avg_profit": 1.0, "win_rate": 54.0},
                    "ranging": {"trade_count": 12, "avg_profit": 0.3, "win_rate": 52.0},
                }
            }
        }
        candidate = {
            "regime_analysis": {
                "per_regime_performance": {
                    "trending": {"trade_count": 15, "avg_profit": 1.1, "win_rate": 53.5},
                    "ranging": {"trade_count": 12, "avg_profit": 0.2, "win_rate": 51.5},
                }
            }
        }

        passed, reason, details = _evaluate_regime_robustness(base, candidate)

        self.assertFalse(passed)
        self.assertIn("avg profit worsened", reason or "")
        self.assertEqual(details["weakest_regime"], "ranging")


if __name__ == "__main__":
    unittest.main()
