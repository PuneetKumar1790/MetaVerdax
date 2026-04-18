"""Standalone carbon calculator shim for demo smoke tests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class CarbonResult:
    co2_saved_kg: float
    energy_saved_kwh: float
    cost_saved_usd: float
    prevented: bool

    def model_dump(self) -> dict[str, Any]:
        return {
            "co2_saved_kg": self.co2_saved_kg,
            "energy_saved_kwh": self.energy_saved_kwh,
            "cost_saved_usd": self.cost_saved_usd,
            "prevented": self.prevented,
        }


class CarbonCalculator:
    def calculate_saved(self, gpu_hours: float, model_size_b: float) -> float:
        return round(max(gpu_hours, 0.0) * max(model_size_b, 0.0) * 0.14, 2)

    def calculate(
        self,
        model_size: str = "medium",
        cloud_provider: str = "aws",
        region: str = "us-east-1",
        prevented: bool = False,
    ) -> CarbonResult:
        base = {"small": 1.8, "medium": 4.6, "large": 9.4}.get(model_size, 4.6)
        provider_multiplier = 1.0 if cloud_provider == "aws" else 1.1
        region_multiplier = 1.0 if region == "us-east-1" else 1.05
        prevented_multiplier = 1.0 if prevented else 0.0
        co2_saved = round(base * provider_multiplier * region_multiplier * prevented_multiplier, 2)
        return CarbonResult(
            co2_saved_kg=co2_saved,
            energy_saved_kwh=round(co2_saved * 2.5, 2),
            cost_saved_usd=round(co2_saved * 3.2, 2),
            prevented=prevented,
        )