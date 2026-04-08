from __future__ import annotations

import unittest
from unittest.mock import patch

from app.services.results.strategy_intelligence_service import (
    INTELLIGENCE_VERSION,
    attach_strategy_intelligence,
    build_strategy_intelligence,
    has_strategy_intelligence,
)


class StrategyIntelligenceFlowTest(unittest.TestCase):
    def test_build_strategy_intelligence_adapts_existing_analysis_without_parallel_schema(self) -> None:
        result = {
            "summary": {
                "startingBalance": 1000,
                "finalBalance": 920,
                "totalProfit": -80,
                "totalProfitPct": -8,
                "totalTrades": 40,
                "tradesPerDay": 2.0,
                "winRate": 42.5,
                "profitFactor": 0.84,
                "maxDrawdown": 18,
            },
            "overview": {},
            "run_metadata": {"backtest_days": 20},
        }
        parent_result = {
            "summary": {
                "startingBalance": 1000,
                "finalBalance": 980,
                "totalProfit": -20,
                "totalProfitPct": -2,
                "totalTrades": 35,
                "winRate": 48,
                "profitFactor": 0.95,
                "maxDrawdown": 11,
            }
        }

        analysis_payload = {
            "root_cause_diagnosis": {
                "primary_failure_mode": "high_loss_rate",
                "primary_failure_label": "High Loss Rate",
                "severity": "critical",
                "root_cause_conclusion": "Entries are poorly timed relative to reversals.",
                "confidence": "medium",
                "confidence_note": "Based on 40 trades.",
                "causal_chain": [{"finding": "42.5% win rate vs 54.0% breakeven"}],
                "fix_priority": ["Tighten entries", "Improve stoploss behavior"],
                "secondary_issues": ["poor_risk_reward: Avg loss exceeds avg win"],
            },
            "weaknesses": [
                {"title": "Weak Trade Quality", "impact": "Win rate and factor imply weak signal quality.", "evidence": "PF 0.84 across 40 trades"},
            ],
            "strengths": [
                {"title": "Good Activity", "evidence": "2.0 trades/day gives enough sample size."},
            ],
            "parameter_recommendations": [
                {
                    "parameter": "stoploss",
                    "suggestion": -0.08,
                    "reason": "Average loss is too large.",
                    "evidence": "Median losing trade = -5.4% while stoploss = -15.0%.",
                    "confidence": "high",
                },
                {
                    "parameter": "trailing_stop",
                    "suggestion": True,
                    "reason": "Lock in profit on winners.",
                    "evidence": "Max drawdown = 18.0% and trailing stop is disabled.",
                    "confidence": "medium",
                },
                {
                    "parameter": "Entry signal threshold",
                    "suggestion": "Tighten entry conditions to improve trade selectivity",
                    "reason": "Poor entries are driving losses.",
                    "evidence": "Win rate = 42.5% with PF 0.84.",
                    "confidence": "low",
                },
            ],
            "health_score": {"total": 41},
            "signal_frequency": {"trades_per_day": 2.0, "diagnosis": "Activity is high enough for evaluation."},
            "exit_quality": {"notes": "Winners are cut early."},
            "overfitting": {"overfitting_risk": "low"},
            "data_warnings": [],
        }

        with patch(
            "app.services.results.strategy_intelligence_service.analyze",
            return_value=analysis_payload,
        ), patch(
            "app.services.results.strategy_intelligence_service.load_strategy_param_metadata",
            return_value={"parameters": [{"name": "stoploss"}, {"name": "trailing_stop"}]},
        ):
            intelligence = build_strategy_intelligence(
                run_id="run-1",
                result=result,
                meta={
                    "parent_run_id": "run-0",
                    "improvement_source": "strategy_intelligence",
                    "strategy_class": "ExampleStrategy",
                },
                parent_result=parent_result,
            )

        self.assertEqual(intelligence["version"], INTELLIGENCE_VERSION)
        self.assertEqual(intelligence["summary"]["trades_per_day"], 2.0)
        self.assertEqual(intelligence["diagnosis"]["primary"]["title"], "High Loss Rate")
        self.assertIn("42.5% win rate", intelligence["diagnosis"]["issues"][0]["evidence"])
        self.assertEqual(intelligence["suggestions"][0]["parameter"], "stoploss")
        self.assertTrue(intelligence["suggestions"][0]["auto_applicable"])
        self.assertEqual(intelligence["suggestions"][0]["action_type"], "quick_param")
        self.assertEqual(intelligence["suggestions"][0]["apply_action"]["target"]["parameter"], "stoploss")
        self.assertEqual(intelligence["suggestions"][2]["action_type"], "manual_guidance")
        self.assertEqual(intelligence["suggestions"][2]["apply_action"]["ai_apply_payload"]["run_context"]["run_id"], "run-1")
        self.assertFalse(intelligence["suggestions"][2]["auto_applicable"])
        self.assertIn("Win rate = 42.5% with PF 0.84.", intelligence["suggestions"][2]["evidence"])
        self.assertEqual(len(intelligence["rerun_plan"]["auto_param_changes"]), 2)
        self.assertIn("Entry signal threshold", intelligence["rerun_plan"]["manual_actions"])
        self.assertEqual(len(intelligence["rerun_plan"]["unsupported_items"]), 1)
        self.assertEqual(intelligence["comparison_to_parent"]["parent_run_id"], "run-0")
        self.assertEqual(intelligence["comparison_to_parent"]["metrics"]["profit_percent"]["diff"], -6.0)
        self.assertEqual(intelligence["iteration_memory"]["improvement_source"], "strategy_intelligence")
        self.assertEqual(intelligence["iteration_memory"]["improvement_applied"], [])

    def test_attach_and_detect_strategy_intelligence(self) -> None:
        enriched = attach_strategy_intelligence({"summary": {}}, {"version": INTELLIGENCE_VERSION})
        self.assertTrue(has_strategy_intelligence(enriched))


if __name__ == "__main__":
    unittest.main()
