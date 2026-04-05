from __future__ import annotations

from enum import Enum


class GoalType(str, Enum):
    maximize_profit = "maximize_profit"
    reduce_drawdown = "reduce_drawdown"
    improve_win_rate = "improve_win_rate"
    balanced = "balanced"


DEFAULT_GOAL = GoalType.balanced

GOAL_LABELS: dict[str, str] = {
    GoalType.maximize_profit.value: "Maximize Profit",
    GoalType.reduce_drawdown.value: "Reduce Drawdown",
    GoalType.improve_win_rate.value: "Improve Win Rate",
    GoalType.balanced.value: "Balanced",
}


LEGACY_GOAL_MAP: dict[str, GoalType] = {
    "higher_profit": GoalType.maximize_profit,
    "maximize_profit": GoalType.maximize_profit,
    "higher_win_rate": GoalType.improve_win_rate,
    "improve_win_rate": GoalType.improve_win_rate,
    "lower_drawdown": GoalType.reduce_drawdown,
    "reduce_drawdown": GoalType.reduce_drawdown,
    "lower_risk": GoalType.reduce_drawdown,
    "cut_losers": GoalType.reduce_drawdown,
    "balanced": GoalType.balanced,
    "auto": GoalType.balanced,
    "compound_growth": GoalType.balanced,
    "more_trades": GoalType.balanced,
    "scalping": GoalType.balanced,
    "swing_trading": GoalType.balanced,
}


GOAL_DIRECTIVES: dict[str, str] = {
    GoalType.maximize_profit.value: """GOAL: Maximize Profit
Prioritize total return, profit factor, expectancy, and upside capture. Push for stronger winners, better ROI schedules, and signal quality that compounds profit without ignoring catastrophic risk.""",
    GoalType.reduce_drawdown.value: """GOAL: Reduce Drawdown
Prioritize max drawdown, recovery factor, downside containment, and capital preservation. Favor tighter risk controls, cleaner exits, and fewer deep loss clusters over aggressive upside.""",
    GoalType.improve_win_rate.value: """GOAL: Improve Win Rate
Prioritize entry quality, signal precision, and the ratio of winning trades to losing trades. Favor cleaner filters, fewer low-conviction entries, and settings that improve hit rate without destroying expectancy.""",
    GoalType.balanced.value: """GOAL: Balanced
Optimize for a balanced outcome across profit, drawdown, and win rate. Recommend changes that improve overall robustness and risk-adjusted performance rather than chasing a single metric.""",
}


def normalize_goal_id(goal_id: str | None) -> str:
    if not goal_id:
        return DEFAULT_GOAL.value
    key = goal_id.strip().lower()
    if not key:
        return DEFAULT_GOAL.value
    if key in GOAL_DIRECTIVES:
        return key
    mapped = LEGACY_GOAL_MAP.get(key)
    if mapped:
        return mapped.value
    return DEFAULT_GOAL.value


def goal_label(goal_id: str | None) -> str:
    normalized = normalize_goal_id(goal_id)
    return GOAL_LABELS.get(normalized, GOAL_LABELS[DEFAULT_GOAL.value])
