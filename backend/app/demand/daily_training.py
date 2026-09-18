"""일별 모델 학습·평가·저장을 한 번에 실행하는 공용 절차. 학습 script와 재학습 script가 함께 쓴다."""
from __future__ import annotations

import re
from datetime import timedelta
from pathlib import Path

import pandas as pd

from app.demand.data import load_daily_visitors
from app.demand.forecasting import build_daily_forecast_dataset, default_split_dates, evaluate_daily_forecast, save_daily_run


PRODUCTION_PATTERN = re.compile(r"^daily-forecast-production-v(\d+)$")


def next_production_directory(root: Path) -> Path:
    """기존 production-v* 최대 번호 + 1 경로. 이미 있으면 덮어쓰지 않도록 오류를 낸다."""
    numbers = [int(match.group(1)) for path in root.glob("daily-forecast-production-v*")
               if path.is_dir() and (match := PRODUCTION_PATTERN.match(path.name))]
    output = root / f"daily-forecast-production-v{max(numbers, default=0) + 1}"
    if output.exists():
        raise FileExistsError("새 모델 폴더가 이미 있습니다.")
    return output


def train_daily_model(visitor_paths: list[Path], output_dir: Path, *, validation_start: str | None = None,
                      test_start: str | None = None) -> dict:
    """원본을 읽어 학습·평가하고 output_dir에 artifact를 저장한 뒤 요약을 돌려준다."""
    if output_dir.exists():
        raise FileExistsError("기존 실행 결과를 보존합니다. 새 출력 경로를 지정하세요.")
    daily, source_audit = load_daily_visitors(visitor_paths)
    frame, feature_audit = build_daily_forecast_dataset(daily)
    data_end = pd.to_datetime(daily.date).max()
    default_validation, default_test = default_split_dates(data_end)
    report, models, predictions = evaluate_daily_forecast(
        frame, validation_start=validation_start or default_validation, test_start=test_start or default_test)
    save_daily_run(output_dir, report, models, predictions, frame, daily,
                   {"source": source_audit, "features": feature_audit}, visitor_paths)
    return {
        "output": str(output_dir), "model_version": report["model_version"], "model_adopted": report["model_adopted"],
        "split": report["split"], "holdout": report["time_holdout"], "interval_80_coverage": report["interval_80_coverage"],
        "checks": report["adoption_checks"], "data_end": data_end.date().isoformat(),
        "last_predictable_target_date": (data_end + timedelta(days=60)).date().isoformat(),
    }
