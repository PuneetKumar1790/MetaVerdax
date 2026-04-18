"""Standalone validator shim for hackathon smoke tests and demo usage."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass
class CheckResult:
    passed: bool
    details: dict[str, Any] = field(default_factory=dict)

    def model_dump(self) -> dict[str, Any]:
        return {"passed": self.passed, **self.details}


@dataclass
class ValidationResult:
    passed: bool
    critical_failures: int
    warnings: int
    anomaly_score: float
    recommendation: str
    checks: dict[str, CheckResult]

    def model_dump(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "critical_failures": self.critical_failures,
            "warnings": self.warnings,
            "anomaly_score": self.anomaly_score,
            "recommendation": self.recommendation,
            "checks": {name: check.model_dump() for name, check in self.checks.items()},
        }


class Validator:
    """Small, dependency-light dataset validator."""

    @staticmethod
    def infer_ranges(df: pd.DataFrame) -> dict[str, dict[str, float]]:
        ranges: dict[str, dict[str, float]] = {}
        for column in df.select_dtypes(include="number").columns:
            series = df[column].dropna()
            if series.empty:
                continue
            ranges[column] = {"min": float(series.min()), "max": float(series.max())}
        return ranges

    def validate(
        self,
        df: pd.DataFrame,
        expected_schema: dict[str, str] | None = None,
        expected_ranges: dict[str, dict[str, float]] | None = None,
    ) -> ValidationResult:
        checks: dict[str, CheckResult] = {}

        schema_passed = True
        schema_details: dict[str, Any] = {"missing_columns": []}
        if expected_schema:
            missing = [column for column in expected_schema if column not in df.columns]
            schema_passed = not missing
            schema_details["missing_columns"] = missing
        checks["schema"] = CheckResult(schema_passed, schema_details)

        null_fraction = float(df.isna().sum().sum() / max(df.size, 1))
        null_passed = null_fraction <= 0.2
        checks["null_check"] = CheckResult(null_passed, {"null_fraction": round(null_fraction, 4)})

        duplicate_rows = int(df.duplicated().sum())
        dup_passed = duplicate_rows == 0
        checks["duplicate_check"] = CheckResult(dup_passed, {"duplicate_rows": duplicate_rows})

        range_violations: dict[str, int] = {}
        for column, bounds in (expected_ranges or {}).items():
            if column not in df.columns or not pd.api.types.is_numeric_dtype(df[column]):
                continue
            series = df[column].dropna()
            violations = int(((series < bounds.get("min", series.min())) | (series > bounds.get("max", series.max()))).sum())
            if violations:
                range_violations[column] = violations
        checks["range_check"] = CheckResult(not range_violations, {"range_violations": range_violations})

        critical_failures = sum(1 for name, check in checks.items() if not check.passed and name in {"schema", "null_check"})
        warnings = sum(1 for name, check in checks.items() if not check.passed and name not in {"schema", "null_check"})
        passed = critical_failures == 0 and warnings == 0
        recommendation = "Approve retraining" if passed else "Block retraining and investigate flagged checks"
        anomaly_score = min(1.0, round(null_fraction + (duplicate_rows / max(len(df), 1)) + (len(range_violations) * 0.1), 4))

        return ValidationResult(
            passed=passed,
            critical_failures=critical_failures,
            warnings=warnings,
            anomaly_score=anomaly_score,
            recommendation=recommendation,
            checks=checks,
        )


DataValidator = Validator