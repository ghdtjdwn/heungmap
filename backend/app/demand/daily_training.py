"""일별 모델 학습·평가·저장을 한 번에 실행하는 공용 절차. 학습 script와 재학습 script가 함께 쓴다."""
from __future__ import annotations

import re
from datetime import timedelta
from pathlib import Path

import pandas as pd

from app.demand.data import load_daily_visitors
from app.demand.forecasting import FEATURES, build_daily_forecast_dataset, default_split_dates, evaluate_daily_forecast, save_daily_run


PRODUCTION_PATTERN = re.compile(r"^daily-forecast-production-v(\d+)$")


def next_production_directory(root: Path) -> Path:
    """기존 production-v* 최대 번호 + 1 경로. 이미 있으면 덮어쓰지 않도록 오류를 낸다."""
    numbers = [int(match.group(1)) for path in root.glob("daily-forecast-production-v*")
               if path.is_dir() and (match := PRODUCTION_PATTERN.match(path.name))]
    output = root / f"daily-forecast-production-v{max(numbers, default=0) + 1}"
    if output.exists():
        raise FileExistsError("새 모델 폴더가 이미 있습니다.")
    return output


def add_festival_ablation(report: dict, baseline_report: dict) -> dict:
    """축제 입력이 있는 모델은 같은 행·분할의 축제 없는 모델보다 전진 검증 WAPE가 좋아야 채택한다."""
    with_festival = report["selected_candidate"]["metrics"]["wape"]
    without = baseline_report["selected_candidate"]["metrics"]["wape"]
    report["ablation"] = {
        "without_festival": {"validation": baseline_report["selected_candidate"]["metrics"],
                             "test": baseline_report["time_holdout"]["model"], "parameters": baseline_report["selected_candidate"]["parameters"]},
        "with_festival": {"validation": report["selected_candidate"]["metrics"], "test": report["time_holdout"]["model"]},
    }
    report["adoption_checks"]["beats_no_festival_validation_wape"] = with_festival < without
    report["model_adopted"] = all(report["adoption_checks"].values())
    report["rejection_reasons"] = [name for name, passed in report["adoption_checks"].items() if not passed]
    return report


def train_daily_model(visitor_paths: list[Path], output_dir: Path, *, validation_start: str | None = None,
                      test_start: str | None = None, festival_paths: list[Path] | None = None) -> dict:
    """원본을 읽어 학습·평가하고 output_dir에 artifact를 저장한 뒤 요약을 돌려준다."""
    if output_dir.exists():
        raise FileExistsError("기존 실행 결과를 보존합니다. 새 출력 경로를 지정하세요.")
    daily, source_audit = load_daily_visitors(visitor_paths)
    calendar = None
    if festival_paths:
        from app.demand.festivals import FESTIVAL_FEATURES, load_festival_calendar

        calendar = load_festival_calendar(festival_paths)
    frame, feature_audit = build_daily_forecast_dataset(daily, calendar)
    data_end = pd.to_datetime(daily.date).max()
    default_validation, default_test = default_split_dates(data_end)
    split = {"validation_start": validation_start or default_validation, "test_start": test_start or default_test}
    features = FEATURES + FESTIVAL_FEATURES if calendar is not None else FEATURES
    report, models, predictions = evaluate_daily_forecast(frame, **split, features=features)
    if calendar is not None:
        baseline_report, _, _ = evaluate_daily_forecast(frame, **split)
        report = add_festival_ablation(report, baseline_report)
        feature_audit["festival_calendar"] = {
            "festivals": len(calendar), "regions": int(calendar.region_code.nunique()),
            "rows_with_active_festival": int((frame.festival_active > 0).sum()),
            "rows_with_festival_in_window": int((frame.festival_days_in_window > 0).sum()), "rows": len(frame),
            "limitations": ["createdtime은 TourAPI 콘텐츠 최초 등록일이라 반복 축제의 올해 일정 공개일보다 이를 수 있습니다.",
                            "수집 시점에 남아 있는 축제만 포함되며 취소·삭제된 축제는 알 수 없습니다."],
        }
    save_daily_run(output_dir, report, models, predictions, frame, daily,
                   {"source": source_audit, "features": feature_audit}, [*visitor_paths, *(festival_paths or [])])
    return {
        "output": str(output_dir), "model_version": report["model_version"], "model_adopted": report["model_adopted"],
        "split": report["split"], "holdout": report["time_holdout"], "interval_80_coverage": report["interval_80_coverage"],
        "checks": report["adoption_checks"], "ablation": report.get("ablation"),
        "festival_calendar": feature_audit.get("festival_calendar"), "data_end": data_end.date().isoformat(),
        "last_predictable_target_date": (data_end + timedelta(days=60)).date().isoformat(),
    }
