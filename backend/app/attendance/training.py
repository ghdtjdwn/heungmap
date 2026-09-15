"""반복 개최 축제 관람수요 모델의 시간 홀드아웃 평가와 원자적 artifact 저장."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor

from app.attendance.data import FEATURES


MODEL_VERSION = "festival-attendance-1.0"
CANDIDATES = (
    {"num_leaves": 5, "min_child_samples": 30, "n_estimators": 120, "learning_rate": 0.03, "model_weight": 0.5},
    {"num_leaves": 7, "min_child_samples": 40, "n_estimators": 150, "learning_rate": 0.03, "model_weight": 0.5},
    {"num_leaves": 11, "min_child_samples": 50, "n_estimators": 150, "learning_rate": 0.03, "model_weight": 0.5},
    {"num_leaves": 7, "min_child_samples": 60, "n_estimators": 180, "learning_rate": 0.02, "model_weight": 0.75},
    {"num_leaves": 7, "min_child_samples": 60, "n_estimators": 180, "learning_rate": 0.02, "model_weight": 1.0},
)


def _model(parameters: dict[str, Any], *, objective: str = "regression_l1", alpha: float | None = None):
    arguments = {
        "objective": objective, "num_leaves": parameters["num_leaves"],
        "min_child_samples": parameters["min_child_samples"], "n_estimators": parameters["n_estimators"],
        "learning_rate": parameters["learning_rate"], "reg_lambda": 2.0,
        "verbosity": -1, "random_state": 42, "n_jobs": 1, "deterministic": True,
        "force_col_wise": True,
    }
    if alpha is not None:
        arguments["alpha"] = alpha
    return LGBMRegressor(**arguments)


def fit_model(frame: pd.DataFrame, parameters: dict[str, Any], *, alpha: float | None = None):
    model = _model(parameters, objective="quantile" if alpha is not None else "regression_l1", alpha=alpha)
    return model.fit(frame[FEATURES], frame["log_residual"])


def predict_attendance(model, frame: pd.DataFrame, parameters: dict[str, Any]) -> np.ndarray:
    residual = np.asarray(model.predict(frame[FEATURES]), dtype=float) * parameters["model_weight"]
    return np.maximum(0.0, np.expm1(np.log1p(frame.prior_attendance.to_numpy(dtype=float)) + residual))


def metrics(actual, predicted) -> dict[str, float | int]:
    actual, predicted = np.asarray(actual, dtype=float), np.asarray(predicted, dtype=float)
    if len(actual) == 0 or (actual <= 0).any() or not np.isfinite([*actual, *predicted]).all():
        raise ValueError("평가값은 비어 있지 않은 유한한 양수 정답이어야 합니다.")
    ratio = predicted / actual
    return {
        "n": len(actual), "mae_people": float(np.mean(np.abs(actual - predicted))),
        "wape": float(np.abs(actual - predicted).sum() / actual.sum()),
        "median_ape": float(np.median(np.abs(actual - predicted) / actual)),
        "rmsle": float(np.sqrt(np.mean((np.log1p(actual) - np.log1p(predicted)) ** 2))),
        "within_factor_2": float(np.mean((ratio >= 0.5) & (ratio <= 2.0))),
    }


def _bootstrap_improvement(actual, baseline, model, *, repetitions: int = 2_000) -> dict[str, float]:
    actual, baseline, model = map(lambda values: np.asarray(values, dtype=float), (actual, baseline, model))
    rng = np.random.default_rng(42)
    differences = []
    for _ in range(repetitions):
        index = rng.integers(0, len(actual), len(actual))
        base_error = np.sqrt(np.mean((np.log1p(actual[index]) - np.log1p(baseline[index])) ** 2))
        model_error = np.sqrt(np.mean((np.log1p(actual[index]) - np.log1p(model[index])) ** 2))
        differences.append((base_error - model_error) / base_error if base_error else 0.0)
    low, high = np.quantile(differences, [0.025, 0.975])
    return {"mean": float(np.mean(differences)), "ci95_low": float(low), "ci95_high": float(high)}


def _subset_report(frame: pd.DataFrame, predictions: np.ndarray) -> dict[str, Any]:
    actual = frame.target_attendance.to_numpy(dtype=float)
    baseline = frame.prior_attendance.to_numpy(dtype=float)
    return {
        "model": metrics(actual, predictions), "prior_year_baseline": metrics(actual, baseline),
        "rmsle_improvement": 1 - metrics(actual, predictions)["rmsle"] / metrics(actual, baseline)["rmsle"],
    }


def evaluate(frame: pd.DataFrame, *, validation_year: int = 2024, test_year: int = 2025):
    train = frame.loc[frame.target_year < validation_year].copy()
    validation = frame.loc[frame.target_year == validation_year].copy()
    test = frame.loc[frame.target_year == test_year].copy()
    if min(len(train), len(validation), len(test)) == 0:
        raise ValueError("학습·검증·최종 시험 연도의 표본이 모두 필요합니다.")
    candidates = []
    for parameters in CANDIDATES:
        model = fit_model(train, parameters)
        prediction = predict_attendance(model, validation, parameters)
        candidates.append({"parameters": parameters, "metrics": metrics(validation.target_attendance, prediction)})
    selected = min(candidates, key=lambda item: (item["metrics"]["rmsle"], item["metrics"]["median_ape"]))
    development = frame.loc[frame.target_year <= validation_year].copy()
    central = fit_model(development, selected["parameters"])
    lower = fit_model(development, selected["parameters"], alpha=0.1)
    upper = fit_model(development, selected["parameters"], alpha=0.9)
    prediction = predict_attendance(central, test, selected["parameters"])
    lower_prediction = predict_attendance(lower, test, selected["parameters"])
    upper_prediction = predict_attendance(upper, test, selected["parameters"])
    lower_prediction = np.minimum(lower_prediction, prediction)
    upper_prediction = np.maximum(upper_prediction, prediction)
    overall = _subset_report(test, prediction)
    subsets = {}
    for measurement in ("계측", "추정", "무응답"):
        mask = test.label_measurement == measurement
        if mask.any():
            subsets[measurement] = _subset_report(test.loc[mask], prediction[mask.to_numpy()])
    actual = test.target_attendance.to_numpy(dtype=float)
    baseline = test.prior_attendance.to_numpy(dtype=float)
    bootstrap = _bootstrap_improvement(actual, baseline, prediction)
    checks = {
        "beats_prior_year_rmsle": overall["model"]["rmsle"] < overall["prior_year_baseline"]["rmsle"],
        "beats_prior_year_median_ape": overall["model"]["median_ape"] < overall["prior_year_baseline"]["median_ape"],
        "bootstrap_ci_excludes_zero": bootstrap["ci95_low"] > 0,
        "measured_subset_not_worse": "계측" in subsets and subsets["계측"]["model"]["rmsle"] <= subsets["계측"]["prior_year_baseline"]["rmsle"],
        "factor_2_coverage_at_least_70pct": overall["model"]["within_factor_2"] >= 0.70,
    }
    report = {
        "schema_version": "1.0", "generated_at": datetime.now(timezone.utc).isoformat(),
        "model_version": MODEL_VERSION, "target": "문체부에 다음 연도 제출된 축제별 전년도 방문객 수(명)",
        "split": {
            "training_target_years": sorted(train.target_year.unique().astype(int).tolist()),
            "validation_target_year": validation_year, "test_target_year": test_year,
            "training_rows": len(train), "validation_rows": len(validation), "test_rows": len(test),
        },
        "candidate_selection": candidates, "selected_candidate": selected,
        "time_holdout": overall, "measurement_subsets": subsets,
        "interval_80_coverage": float(np.mean((actual >= lower_prediction) & (actual <= upper_prediction))),
        "bootstrap_rmsle_improvement": bootstrap, "adoption_checks": checks,
        "model_adopted": all(checks.values()),
        "rejection_reasons": [name for name, passed in checks.items() if not passed],
        "limitations": [
            "정답은 지자체 보고 방문객 수이며 티켓 발권 인원이나 고유 방문자와 다를 수 있습니다.",
            "2025년 정답의 계측 방법만 분리 가능하며 이전 연도는 계측·추정 여부를 알 수 없습니다.",
            "동일 축제의 전년도 실적을 입력으로 쓰므로 신규 축제에는 적용하지 않습니다.",
            "최종 시험연도는 후보 선택이나 하이퍼파라미터 조정에 사용하지 않았습니다.",
        ],
    }
    predictions = test[["event_key", "title", "province", "district", "target_year", "label_measurement",
                        "prior_attendance", "target_attendance"]].copy()
    predictions["p10"], predictions["p50"], predictions["p90"] = lower_prediction, prediction, upper_prediction
    return report, (lower, central, upper), predictions


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def save_run(output_dir: Path, report: dict[str, Any], models, predictions: pd.DataFrame,
             frame: pd.DataFrame, records: pd.DataFrame, audit: dict[str, Any], source_paths: list[Path]):
    output_dir.mkdir(parents=True, exist_ok=False)
    for name, model in zip(("p10", "p50", "p90"), models):
        model.booster_.save_model(str(output_dir / f"{name}.txt"))
    predictions.to_csv(output_dir / "holdout-predictions.csv", index=False)
    frame.to_csv(output_dir / "training.csv", index=False)
    catalog = records.loc[records.plan_year == records.plan_year.max()].copy()
    catalog.to_csv(output_dir / "catalog.csv", index=False)
    report["data_audit"] = audit
    material = "".join(file_digest(output_dir / name) for name in ("p10.txt", "p50.txt", "p90.txt", "catalog.csv"))
    report["model_version"] = MODEL_VERSION + "-" + hashlib.sha256(material.encode()).hexdigest()[:12]
    (output_dir / "evaluation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    manifest = {
        "schema_version": "1.0", "model_version": report["model_version"],
        "created_at": report["generated_at"], "model_adopted": report["model_adopted"],
        "features": FEATURES, "parameters": report["selected_candidate"]["parameters"],
        "catalog_year": int(records.plan_year.max()),
        "source_files": [{"name": path.name, "sha256": file_digest(path)} for path in source_paths],
        "files": {name: file_digest(output_dir / name) for name in ("p10.txt", "p50.txt", "p90.txt", "catalog.csv", "evaluation.json")},
        "limitations": report["limitations"],
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")

