"""채택 모델을 학습·후보 선택에 쓰지 않은 새 관측일에 그대로 채점하는 전향 평가."""
from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd

from app.demand.daily_service import predict_rows
from app.demand.forecasting import InsufficientForecastHistory, make_forecast_features, metrics


def size_quintiles(frame: pd.DataFrame, prediction: str = "p50") -> list[dict]:
    """실제 방문자 규모 5분위별 오차. 작은 지역일수록 오차가 큰지 확인한다."""
    if len(frame) < 5:
        return []
    groups = pd.qcut(frame.target.rank(method="first"), 5, labels=False)
    rows = []
    for index, group in frame.groupby(groups):
        error = (group[prediction] - group.target).abs()
        rows.append({"quintile": int(index) + 1, "n": len(group), "mean_actual": float(group.target.mean()),
                     "wape": float(error.sum() / group.target.sum()), "median_ape": float((error / group.target).median())})
    return rows


def region_errors(frame: pd.DataFrame, prediction: str = "p50") -> pd.DataFrame:
    """시군구별 WAPE와 관측 일수."""
    grouped = frame.assign(error=(frame[prediction] - frame.target).abs()).groupby("region_code")
    return pd.DataFrame({"region_name": grouped.region_name.last(), "wape": grouped.error.sum() / grouped.target.sum(),
                         "days": grouped.size()}).sort_values("wape", ascending=False)


def evaluate_frozen(manifest: dict, models, daily: pd.DataFrame, start) -> tuple[dict, pd.DataFrame]:
    """start 이후 관측일마다 서비스와 같은 입력·수식으로 예측해 기준선과 비교한다."""
    start = pd.Timestamp(start).normalize()
    daily = daily.copy()
    daily["date"] = pd.to_datetime(daily.date)
    regions = {str(item["code"]) for item in manifest["regions"]}
    rows, baselines, inputs, skipped = [], [], [], 0
    for code, history in daily.loc[daily.region_code.astype(str).isin(regions)].groupby("region_code"):
        for _, target in history.loc[history.date >= start].iterrows():
            try:
                values, baseline = make_forecast_features(target.date, history)
            except InsufficientForecastHistory:
                skipped += 1
                continue
            rows.append({"date": target.date, "region_code": str(code), "region_name": target.region_name,
                         "target": float(target.visitor_count)})
            baselines.append(baseline)
            inputs.append(values)
    if not rows:
        raise ValueError("전향 평가할 새 관측일이 없습니다.")
    frame = pd.DataFrame(rows)
    frame["baseline"] = baselines
    low, center, high, _ = predict_rows(models, manifest, pd.DataFrame(inputs), baselines)
    frame["p10"], frame["p50"], frame["p90"] = low, center, high
    model_metrics, baseline_metrics = metrics(frame.target, frame.p50), metrics(frame.target, frame.baseline)
    worst = region_errors(frame).head(10)
    report = {
        "schema_version": "1.0", "model_version": manifest["model_version"],
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "period": {"start": frame.date.min().date().isoformat(), "end": frame.date.max().date().isoformat()},
        "days": int(frame.date.nunique()), "rows": len(frame), "regions": int(frame.region_code.nunique()),
        "skipped_rows": skipped, "model": model_metrics, "seasonal_growth_baseline": baseline_metrics,
        "wape_improvement": 1 - model_metrics["wape"] / baseline_metrics["wape"],
        "interval_80_coverage": float(np.mean((frame.target >= frame.p10) & (frame.target <= frame.p90))),
        "by_size_quintile": size_quintiles(frame),
        "worst_regions": [{"region_code": code, **{k: (float(v) if k == "wape" else v) for k, v in row.items()}}
                          for code, row in worst.to_dict("index").items()],
        "note": "모델 data_end 이후 관측일이며 학습·후보 선택·보정에 사용하지 않은 전향 평가입니다.",
    }
    return report, frame
