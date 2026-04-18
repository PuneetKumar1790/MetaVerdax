"""Standalone anomaly scorer shim for demo smoke tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class AnomalyScore:
    score: float
    action: str
    recommendation: str
    breakdown: dict[str, Any] = field(default_factory=dict)
    anomaly_rate: float = 0.0

    def model_dump(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "action": self.action,
            "recommendation": self.recommendation,
            "breakdown": self.breakdown,
            "anomaly_rate": self.anomaly_rate,
        }


class AnomalyScorer:
    def score(self, data: Any, drift_result: Any | None = None) -> AnomalyScore:
        if isinstance(data, list):
            values = np.asarray(data, dtype=float)
            if values.size == 0:
                return AnomalyScore(0.0, "approve", "No anomalies detected", {"outliers": []}, 0.0)
            median = float(np.median(values))
            mad = float(np.median(np.abs(values - median))) or 1.0
            z_like = np.abs(values - median) / (1.4826 * mad)
            outliers = np.where(z_like > 3.5)[0].tolist()
            score = min(1.0, round(len(outliers) / max(len(values), 1), 4) * 5)
            action = "block" if score >= 0.4 else "review" if score >= 0.2 else "approve"
            recommendation = "Investigate anomalies before retraining" if action != "approve" else "Proceed with retraining"
            return AnomalyScore(score, action, recommendation, {"outliers": outliers, "median": median}, round(len(outliers) / max(len(values), 1), 4))

        validation = data if isinstance(data, dict) else {}
        drift = drift_result if isinstance(drift_result, dict) else {}
        critical_failures = float(validation.get("critical_failures", 0))
        warnings = float(validation.get("warnings", 0))
        drift_score = float(drift.get("drift_score", 0.0))
        anomaly_rate = min(1.0, float(validation.get("anomaly_score", 0.0)) + drift_score * 0.5)
        score = min(1.0, round((critical_failures * 0.35) + (warnings * 0.08) + drift_score * 0.4 + anomaly_rate * 0.3, 4))
        action = "block" if score >= 0.5 else "review" if score >= 0.25 else "approve"
        recommendation = "Block retraining and remediate quality issues" if action == "block" else "Review dataset before retraining" if action == "review" else "Dataset appears safe"
        return AnomalyScore(score, action, recommendation, {"critical_failures": critical_failures, "warnings": warnings, "drift_score": drift_score}, anomaly_rate)