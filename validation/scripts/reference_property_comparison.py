"""Compare public RHS tabulated properties through the cantilever equations.

This is a reference-property check, not a rounded-geometry validation. The
source table does not publish a corner radius, so its properties are used as
tabulated inputs and are never passed as guessed geometry to the project tool.
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "steel_for_life_hfrhs_reference.csv"
OUTPUT = ROOT / "results" / "steel_for_life_hfrhs_reference_comparison.json"

LOAD_N = 500.0
LENGTH_MM = 400.0
E_MPA = 200_000.0
DENSITY_KG_M3 = 7_850.0
YIELD_MPA = 235.0


def relative_error(actual: float, reference: float) -> float:
    return abs(actual - reference) / abs(reference) if reference else 0.0


def main() -> None:
    rows = []
    with SOURCE.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            area_mm2 = float(row["area_cm2"]) * 100.0
            inertia_mm4 = float(row["major_inertia_cm4"]) * 10_000.0
            modulus_mm3 = float(row["major_modulus_cm3"]) * 1_000.0
            mass_per_m = float(row["mass_kg_per_m"])
            stress_mpa = LOAD_N * LENGTH_MM / modulus_mm3
            deflection_mm = LOAD_N * LENGTH_MM**3 / (3.0 * E_MPA * inertia_mm4)
            mass_kg = mass_per_m * LENGTH_MM / 1000.0
            area_mass_kg_per_m = DENSITY_KG_M3 * area_mm2 * 1e-6
            rows.append(
                {
                    "source_record": row["source_record"],
                    "input": {
                        "load_n": LOAD_N,
                        "length_mm": LENGTH_MM,
                        "material_reference": "S235工程参考参数（E=200 GPa，rho=7850 kg/m3，fy=235 MPa）",
                        "major_axis": "表格第一惯性矩/截面模量列，按 h 为弯曲高度",
                    },
                    "tabulated_properties": {
                        "area_mm2": area_mm2,
                        "major_inertia_mm4": inertia_mm4,
                        "major_modulus_mm3": modulus_mm3,
                        "mass_kg_per_m": mass_per_m,
                    },
                    "derived_response": {
                        "max_stress_mpa": stress_mpa,
                        "max_deflection_mm": deflection_mm,
                        "mass_kg": mass_kg,
                        "yield_safety_factor": YIELD_MPA / stress_mpa,
                    },
                    "internal_consistency": {
                        "mass_per_m_from_area_kg_per_m": area_mass_kg_per_m,
                        "mass_per_m_relative_error": relative_error(area_mass_kg_per_m, mass_per_m),
                        "mass_per_m_consistent_with_density": relative_error(area_mass_kg_per_m, mass_per_m) <= 0.01,
                        "section_modulus_consistent_with_I_over_H2": relative_error(inertia_mm4 / (float(row["height_mm"]) / 2.0), modulus_mm3) <= 0.02,
                    },
                }
            )
    result = {
        "ok": True,
        "validation_type": "public_reference_property_comparison",
        "source": "SCI / Steel for Life Interactive Blue Book, hot-finished RHS, BS EN 10210-2:2006",
        "source_file": "validation/sources/steel_for_life_hfrhs_table_2026-10-11.html",
        "not_experimental": True,
        "rounded_radius_validation": False,
        "limitations": [
            "公开表未提供圆角半径，因此未将其规格反推为当前圆角几何工具输入",
            "本结果验证表格属性驱动的悬臂梁公式链路，不验证制造圆角、焊缝、残余应力或规范完整验算",
        ],
        "cases": rows,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
