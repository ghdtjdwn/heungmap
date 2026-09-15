"""시간 순서를 보존하는 모델 선택, 최종 평가 및 네이티브 모델 저장."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, median_absolute_error, root_mean_squared_error
from sklearn.model_selection import GroupKFold

from app.demand.data import FEATURES

SEED = 20260915
LABEL = "uplift_rate"
MODEL_VERSION = "regional-demand-1.0"


def metrics(actual, predicted) -> dict:
    actual, predicted = np.asarray(actual), np.asarray(predicted)
    return {
        "rows": len(actual),
        "mae": float(mean_absolute_error(actual, predicted)),
        "median_ae": float(median_absolute_error(actual, predicted)),
        "rmse": float(root_mean_squared_error(actual, predicted)),
        "bias": float(np.mean(predicted - actual)),
    }


def temporal_split(frame: pd.DataFrame, start, end=None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """모든 학습 label이 첫 평가 행의 D-30 시점까지 공개됐어야 한다."""
    start = pd.Timestamp(start)
    test = frame[frame.start_date >= start]
    if end is not None:
        test = test[test.start_date < pd.Timestamp(end)]
    knowledge_cutoff = start - pd.Timedelta(days=30)
    train = frame[frame.label_available_date <= knowledge_cutoff]
    train = train[~train.group_id.isin(test.group_id)]
    return train.copy(), test.copy()


def baselines(train, test) -> dict[str, np.ndarray]:
    global_median = float(train[LABEL].median())
    regional = test.region_code.map(train.groupby("region_code")[LABEL].median()).fillna(global_median)
    return {
        "zero_change": np.zeros(len(test)),
        "global_median": np.full(len(test), global_median),
        "region_median": regional.to_numpy(),
        "weekday_history": test["calendar_expected_uplift"].to_numpy(),
    }


def candidate_specs() -> list[dict]:
    # 탐색 범위를 먼저 고정한다. 최종 평가 성능으로 재선택하지 않는다.
    return [
        {"objective": "regression_l1", "num_leaves": leaves, "n_estimators": trees,
         "min_child_samples": child, "residual": residual, "model_weight": weight}
        for leaves, child in ((3, 15), (7, 15), (7, 30))
        for trees in (100, 300)
        for residual in (False, True)
        for weight in (.25, .5, .75, 1.0)
    ]


def fit_model(frame, spec, *, alpha=None):
    parameters = {key: value for key, value in spec.items() if key not in {"residual", "model_weight"}}
    if alpha is not None:
        parameters.update(objective="quantile", alpha=alpha)
    estimator = lgb.LGBMRegressor(
        **parameters, learning_rate=0.03, reg_lambda=5.0, max_depth=-1,
        verbosity=-1, random_state=SEED, n_jobs=1, deterministic=True, force_col_wise=True,
    )
    target = frame[LABEL].to_numpy().copy()
    if spec["residual"]:
        target -= frame.calendar_expected_uplift.to_numpy()
    estimator.fit(frame[FEATURES], target)
    return estimator


def predict_model(model, frame, spec):
    prediction = np.asarray(model.predict(frame[FEATURES]))
    weight = spec.get("model_weight", 1.0)
    if spec["residual"]:
        prediction = prediction + frame.calendar_expected_uplift.to_numpy()
    prediction = weight * prediction + (1 - weight) * frame.calendar_expected_uplift.to_numpy()
    return np.maximum(-1, prediction)


def time_folds(development):
    # 월 경계와 공개 지연을 적용한다. 행 단위 TimeSeriesSplit은 중복 날짜를 나눌 수 있다.
    boundaries = sorted(development.start_date.dt.to_period("M").unique())
    folds = []
    for month in boundaries:
        start, end = month.start_time, (month + 1).start_time
        train, valid = temporal_split(development, start, end)
        if len(train) >= 60 and len(valid) >= 8:
            folds.append((train, valid))
    if len(folds) < 2:
        raise ValueError("시간 검증에 충분한 과거 학습·평가 기간이 없습니다.")
    return folds


def search(development):
    folds = time_folds(development)
    results = []
    for index, spec in enumerate(candidate_specs()):
        actual, predictions, errors, details = [], [], [], []
        for train, valid in folds:
            predicted = predict_model(fit_model(train, spec), valid, spec)
            actual.extend(valid[LABEL]); predictions.extend(predicted)
            errors.extend(valid[LABEL].to_numpy() - predicted)
            details.append({"validation_start": valid.start_date.min().date().isoformat(),
                            "train_rows": len(train), "last_training_label_available": train.label_available_date.max().date().isoformat(),
                            **metrics(valid[LABEL], predicted)})
        result = {"candidate_id": index, "parameters": spec, "validation": metrics(actual, predictions),
                  "folds": details, "residual_quantiles": np.quantile(errors, [0.1, 0.9]).tolist()}
        results.append(result)
        print(json.dumps({"candidate": index + 1, "of": len(candidate_specs()),
                          "validation_mae": result["validation"]["mae"]}), flush=True)
    ranked = sorted(results, key=lambda item: (item["validation"]["mae"], item["candidate_id"]))
    return ranked[0], ranked


def uncertainty(models, frame, spec, residual_quantiles):
    center = predict_model(models[1], frame, spec)
    lower = np.minimum(predict_model(models[0], frame, spec), center + min(0, residual_quantiles[0]))
    upper = np.maximum(predict_model(models[2], frame, spec), center + max(0, residual_quantiles[1]))
    return np.column_stack((np.maximum(-1, lower), center, upper))


def interval_metrics(actual, intervals):
    actual = np.asarray(actual)
    return {
        "nominal_coverage": 0.8,
        "empirical_coverage": float(np.mean((actual >= intervals[:, 0]) & (actual <= intervals[:, 2]))),
        "mean_width": float(np.mean(intervals[:, 2] - intervals[:, 0])),
        "method": "native_quantiles_expanded_by_development_time_oof_residuals",
        "limitation": "시간 변화에 대한 포함률 보장이 아닌 개발 기간 오차로 보정한 경험적 범위",
    }


def cluster_bootstrap(actual, predicted, baseline, groups, *, repetitions=2000):
    """겹친 행사 오차의 독립성을 가정하지 않고 지역 단위로 재표집한다."""
    differences = np.abs(np.asarray(actual) - baseline) - np.abs(np.asarray(actual) - predicted)
    grouped = pd.DataFrame({"group": np.asarray(groups), "gain": differences}).groupby("group").gain.agg(["sum", "count"])
    rng = np.random.default_rng(SEED)
    draws = rng.integers(0, len(grouped), size=(repetitions, len(grouped)))
    means = grouped["sum"].to_numpy()[draws].sum(axis=1) / grouped["count"].to_numpy()[draws].sum(axis=1)
    return {"unit": "region", "repetitions": repetitions, "mae_gain_95_percent_interval": np.quantile(means, [0.025, 0.975]).tolist()}


def evaluate(frame, *, test_start="2026-07-01"):
    development, test = temporal_split(frame, test_start)
    if len(development) < 100 or len(test) < 40:
        raise ValueError("개발 100행과 최종 시간 평가 40행 이상이 필요합니다.")
    winner, leaderboard = search(development)
    spec = winner["parameters"]
    models = [fit_model(development, spec, alpha=.1), fit_model(development, spec), fit_model(development, spec, alpha=.9)]
    predictions = predict_model(models[1], test, spec)
    baseline_predictions = baselines(development, test)
    baseline_metrics = {name: metrics(test[LABEL], values) for name, values in baseline_predictions.items()}
    result_metrics = metrics(test[LABEL], predictions)
    intervals = uncertainty(models, test, spec, winner["residual_quantiles"])
    interval_result = interval_metrics(test[LABEL], intervals)
    group_results = []
    # 미래 평가 지역의 행사 label을 제외한다. 해당 지역의 선행 방문자 이력은 사용한다.
    splitter = GroupKFold(n_splits=5)
    for fold, (_, indices) in enumerate(splitter.split(test, groups=test.region_code), 1):
        group_test = test.iloc[indices]
        group_train = development[~development.region_code.isin(group_test.region_code)]
        model = fit_model(group_train, spec)
        group_predictions = predict_model(model, group_test, spec)
        group_results.append({"fold": fold, "train_rows": len(group_train),
                              "model": metrics(group_test[LABEL], group_predictions),
                              "global_median": metrics(group_test[LABEL], baselines(group_train, group_test)["global_median"])})
    group_model_mae = sum(x["model"]["mae"] * x["model"]["rows"] for x in group_results) / len(test)
    group_baseline_mae = sum(x["global_median"]["mae"] * x["model"]["rows"] for x in group_results) / len(test)
    reference = baseline_metrics["region_median"]
    improvement = 1 - result_metrics["mae"] / reference["mae"] if reference["mae"] else 0
    checks = {
        "time_mae_improves_region_baseline_by_10_percent": improvement >= .1,
        "time_rmse_not_worse_than_region_baseline": result_metrics["rmse"] <= reference["rmse"],
        "time_mae_not_worse_than_weekday_history": result_metrics["mae"] <= baseline_metrics["weekday_history"]["mae"],
        "unseen_region_future_mae_not_worse": group_model_mae <= group_baseline_mae,
        "interval_coverage_at_least_70_percent": interval_result["empirical_coverage"] >= .7,
        "at_least_40_future_test_rows": len(test) >= 40,
    }
    by_month, by_region = {}, {}
    errors = test.assign(predicted=predictions)
    for key, part in errors.groupby(errors.start_date.dt.strftime("%Y-%m")):
        by_month[key] = metrics(part[LABEL], part.predicted)
    for key, part in errors.groupby("region_code"):
        by_region[key] = metrics(part[LABEL], part.predicted)
    report = {
        "report_version": "2.0", "generated_at": datetime.now(timezone.utc).isoformat(),
        "model_version": MODEL_VERSION, "seed": SEED,
        "experiment_note": "초기L2실험 이후 p50 의미에 맞는 L1과 개발자료 전용 축소 정규화로 교정. 같은 후향 평가기간을 재사용하며 신규 독립 평가가 아님.",
        "target": "행사 직전28일 중앙값 대비 행사 기간 일평균 지역 방문수요 증감률(비율)",
        "features": FEATURES, "selected_candidate": winner, "leaderboard": leaderboard,
        "training_scope": {"regions": sorted(development.region_code.unique().tolist()),
                           "feature_ranges": {name: [float(development[name].min()), float(development[name].max())] for name in FEATURES}},
        "split": {"test_start": test_start, "train_rows": len(development), "test_rows": len(test),
                  "train_last_event_end": development.end_date.max().date().isoformat(),
                  "train_last_label_available": development.label_available_date.max().date().isoformat(),
                  "test_first_prediction_as_of": test.prediction_as_of.min().date().isoformat(),
                  "test_last_event_end": test.end_date.max().date().isoformat(),
                  "excluded_between_train_and_test": len(frame) - len(development) - len(test)},
        "time_holdout": {"baselines": baseline_metrics, "model": result_metrics, "mae_improvement_rate": improvement,
                         "interval": interval_result, "by_month": by_month, "by_region": by_region,
                         "bootstrap": cluster_bootstrap(test[LABEL], predictions, baseline_predictions["region_median"], test.region_code)},
        "future_unseen_region": {"folds": group_results, "model_mae": group_model_mae, "baseline_mae": group_baseline_mae,
                                 "scope": "평가 지역의 행사 label을 fold 학습에서 제외. 선행 방문자 이력은 사용하며 후보 선택은 공통 개발 자료에서 수행."},
        "adoption_checks": checks, "model_adopted": all(checks.values()),
        "rejection_reasons": [key for key, value in checks.items() if not value],
        "limitations": [
            "지역 방문자-일 집계이며 축제 입장객·인과적 행사 효과·티켓 수요·실제 혼잡이 아닙니다.",
            "과거 API 공개시점 snapshot이 없어 방문자 공개 지연30일을 가정한 후향 평가입니다.",
            "TourAPI 행사 일정은 사후 수집됐으므로 당시 공지·취소·일정변경을 완벽히 재현하지 못합니다.",
            "과거 v1 평가에서 사용한 자료를 포함하며 신규 전향 평가로 해석할 수 없습니다.",
            "모델 선택은 개발 기간만 사용했고 최종 평가 결과로 후보를 다시 선택하지 않았습니다.",
            "80% 범위는 개발 시간검증 오차와 분위수 예측으로 계산하며 미래 포함률을 보장하지 않습니다.",
        ],
    }
    audit_predictions = test[["event_id", "group_id", "region_code", "start_date", "end_date", LABEL]].copy()
    audit_predictions[["p10", "p50", "p90"]] = intervals
    for name, values in baseline_predictions.items():
        audit_predictions[name] = values
    return report, models, audit_predictions


def file_digest(path: Path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def save_run(output_dir: Path, report, models, predictions, frame, daily, audit, source_paths):
    # 완료 manifest는 마지막에 기록한다. 덜 쓰인 artifact는 serving에서 읽지 않는다.
    output_dir.mkdir(parents=True, exist_ok=False)
    for name, model in zip(("p10", "p50", "p90"), models):
        model.booster_.save_model(str(output_dir / f"{name}.txt"))
    daily.to_csv(output_dir / "history.csv", index=False)
    frame.to_csv(output_dir / "training.csv", index=False)
    predictions.to_csv(output_dir / "holdout-predictions.csv", index=False)
    # 같은 코드라도 학습 파일·입력 이력이 달라지면 비교 가능한 모델 버전도 달라진다.
    version_material = "".join(file_digest(output_dir / name) for name in ("p10.txt", "p50.txt", "p90.txt", "history.csv"))
    version_material += json.dumps(report["selected_candidate"], sort_keys=True)
    report["model_version"] = MODEL_VERSION + "-" + hashlib.sha256(version_material.encode()).hexdigest()[:12]
    report["data_audit"] = audit
    (output_dir / "evaluation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    region_names = daily.drop_duplicates("region_code").set_index("region_code").region_name.to_dict()
    manifest = {
        "schema_version": "1.0", "model_version": report["model_version"], "created_at": report["generated_at"],
        "model_adopted": report["model_adopted"], "features": FEATURES,
        "parameters": report["selected_candidate"]["parameters"],
        "residual_quantiles": report["selected_candidate"]["residual_quantiles"],
        "training_end": report["split"]["train_last_event_end"],
        "data_end": daily.date.max().date().isoformat(),
        "festival_retrieved_at": audit["festival_retrieved_at_max"],
        "training_scope": report["training_scope"],
        "regions": [{"code": code, "name": region_names.get(code, code)} for code in sorted(frame.region_code.unique())],
        "source_files": [{"name": path.name, "sha256": file_digest(path)} for path in source_paths],
        "files": {name: file_digest(output_dir / name) for name in ("p10.txt", "p50.txt", "p90.txt", "history.csv", "evaluation.json")},
        "limitations": report["limitations"],
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
