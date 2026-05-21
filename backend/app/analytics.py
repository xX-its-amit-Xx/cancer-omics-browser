"""Survival analytics built on lifelines.

Given two patient groups (mutated vs wild-type for a gene) with overall-survival
time and event flags, compute Kaplan-Meier curves and a log-rank p-value.
"""
from lifelines import KaplanMeierFitter
from lifelines.statistics import logrank_test


def km_curve(times: list[float], events: list[int]) -> tuple[list[float], list[float]]:
    """Return (timeline, survival_probability) for one group."""
    if not times:
        return [], []
    kmf = KaplanMeierFitter()
    kmf.fit(times, event_observed=events)
    timeline = [float(t) for t in kmf.survival_function_.index.tolist()]
    survival = [float(v) for v in kmf.survival_function_["KM_estimate"].tolist()]
    return timeline, survival


def logrank_pvalue(
    times_a: list[float],
    events_a: list[int],
    times_b: list[float],
    events_b: list[int],
) -> float | None:
    """Two-group log-rank test p-value, or None if either group is empty."""
    if not times_a or not times_b:
        return None
    result = logrank_test(times_a, times_b, event_observed_A=events_a, event_observed_B=events_b)
    return float(result.p_value)
