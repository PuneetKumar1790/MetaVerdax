"""Standalone drift detector shim for demo smoke tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

import pandas as pd


@dataclass
class DriftResult:
    drift_detected: bool
    drifted_features: list[str]
    feature_details: dict[str, dict[str, Any]] = field(default_factory=dict)
    drift_severity: str = "LOW"
    isolation_forest_anomaly_ratio: float = 0.0
    isolation_forest_delta: float = 0.0
    drift_score: float = 0.0

    def model_dump(self) -> dict[str, Any]:
        return {
            "drift_detected": self.drift_detected,
            "drifted_features": self.drifted_features,
            "feature_details": self.feature_details,
            "drift_severity": self.drift_severity,
            "isolation_forest_anomaly_ratio": self.isolation_forest_anomaly_ratio,
            "isolation_forest_delta": self.isolation_forest_delta,
            "drift_score": self.drift_score,
        }


class DriftDetector:
    """Very small drift detector that works with dicts or DataFrames."""

    def detect(self, reference: Any, current: Any | None = None) -> DriftResult:
        if isinstance(reference, pd.DataFrame):
            return self._detect_from_dataframe(reference)

        if isinstance(reference, Mapping) and isinstance(current, Mapping):
            return self._detect_from_mappings(reference, current)

        return DriftResult(False, [], {}, "LOW", 0.0, 0.0, 0.0)

    def _detect_from_mappings(self, reference: Mapping[str, Any], current: Mapping[str, Any]) -> DriftResult:
        drifted: list[str] = []
        details: dict[str, dict[str, Any]] = {}

        for key in sorted(set(reference) & set(current)):
            ref_values = pd.Series(reference[key]).dropna()
            cur_values = pd.Series(current[key]).dropna()
            if ref_values.empty or cur_values.empty:
                continue
            ref_mean = float(ref_values.mean())
            cur_mean = float(cur_values.mean())
            denom = abs(ref_mean) + 1e-9
            delta = abs(cur_mean - ref_mean) / denom
            details[key] = {"reference_mean": ref_mean, "current_mean": cur_mean, "relative_delta": round(delta, 4)}
            if delta > 0.25:
                drifted.append(key)

        drift_score = round(len(drifted) / max(len(details), 1), 4)
        severity = "CRITICAL" if drift_score >= 0.6 else "REVIEW" if drift_score >= 0.3 else "LOW"
        anomaly_ratio = min(1.0, drift_score * 0.8)
        return DriftResult(bool(drifted), drifted, details, severity, anomaly_ratio, drift_score / 2, drift_score)

    def _detect_from_dataframe(self, df: pd.DataFrame) -> DriftResult:
        numeric = df.select_dtypes(include="number")
        if numeric.empty:
            return DriftResult(False, [], {}, "LOW", 0.0, 0.0, 0.0)

        drifted: list[str] = []
        details: dict[str, dict[str, Any]] = {}
        for column in numeric.columns:
            series = numeric[column].dropna()
            if series.empty:
                continue
            spread = float(series.std(ddof=0))
            mean = float(series.mean())
            score = 0.0 if abs(mean) < 1e-9 else min(1.0, spread / (abs(mean) + 1e-9))
            details[column] = {"mean": mean, "std": spread, "score": round(score, 4)}
            if score > 0.5:
                drifted.append(column)

        drift_score = round(len(drifted) / max(len(details), 1), 4)
        severity = "CRITICAL" if drift_score >= 0.6 else "REVIEW" if drift_score >= 0.3 else "LOW"
        anomaly_ratio = min(1.0, drift_score * 0.75)
        return DriftResult(bool(drifted), drifted, details, severity, anomaly_ratio, drift_score / 3, drift_score)