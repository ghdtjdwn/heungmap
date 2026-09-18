"""방문자 자료 수집과 정기 재학습 판단. 매일 실행해도 새 자료가 충분할 때만 재학습한다."""
from __future__ import annotations

import asyncio
import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from app.demand import daily_service
from app.demand.daily_training import next_production_directory, train_daily_model
from app.demand.training_inputs import default_visitor_paths, latest_raw_date


MIN_NEW_DAYS = 7          # 모델 자료 기준일보다 7일 이상 새 자료가 쌓이면 재학습한다.
STALE_MARGIN_DAYS = 21    # 노후까지 21일 이하로 남으면 새 자료가 하루라도 있으면 재학습한다.
WARN_DAYS = 14            # 재학습 후에도 노후까지 14일 이하면 경고 종료 코드를 낸다.


def collect_new_visitors(raw_dir: Path, today: date) -> dict:
    """마지막 원본 기준일 다음 날부터 오늘까지 append-only로 받는다. 겹쳐 받지 않는다."""
    from app.data_gate.cli import collect

    start = latest_raw_date(default_visitor_paths(raw_dir)) + timedelta(days=1)
    if start > today:
        return {"status": "no_new_data", "requested_from": start.isoformat()}
    # 시작일을 이름에 넣어 같은 날 다시 실행해도 같은 조건의 파일만 이어받는다.
    output = raw_dir / f"visitors-{start:%Y%m%d}-{today:%Y%m%d}-refresh-{today:%Y%m%d}.jsonl"
    asyncio.run(collect("visitors", f"{start:%Y%m%d}", f"{today:%Y%m%d}", output, max_pages=20, rows=10000))
    if not output.exists() or latest_raw_date([output]) < start:
        output.unlink(missing_ok=True)  # 빈 응답 페이지만 담긴 파일은 남기지 않는다.
        return {"status": "no_new_data", "requested_from": start.isoformat()}
    return {"status": "collected", "file": output.name, "from": start.isoformat(), "to": latest_raw_date([output]).isoformat()}


def _forward_evaluate(directory: Path, data_end: date, today: date) -> dict | None:
    """재학습 전에 현재 모델을 새 관측일로 채점해 모델 폴더에 남긴다(이미 있으면 건너뜀)."""
    from app.demand.data import load_daily_visitors
    from app.demand.forward_evaluation import evaluate_frozen

    output = directory / f"forward-evaluation-{today:%Y%m%d}.json"
    if output.exists():
        return {"output": output.name, "skipped": "already_exists"}
    manifest, models, _ = daily_service._artifact()
    daily, _ = load_daily_visitors(default_visitor_paths())
    try:
        report, _ = evaluate_frozen(manifest, models, daily, data_end + timedelta(days=1))
    except ValueError as exc:  # 새 관측일이 모델 지역에 없으면 평가하지 않는다.
        return {"skipped": str(exc)}
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return {"output": output.name, "period": report["period"], "model_wape": report["model"]["wape"],
            "baseline_wape": report["seasonal_growth_baseline"]["wape"], "rows": report["rows"]}


def run_scheduled_refresh(*, raw_dir: Path, output_root: Path, today: date, collect: bool = True,
                          min_new_days: int = MIN_NEW_DAYS, stale_margin_days: int = STALE_MARGIN_DAYS) -> dict:
    """수집 → 재학습 필요 판단 → (전향 평가 → 재학습) → 상태 확인. 결과 요약을 돌려준다."""
    result: dict = {"run_at": datetime.now(timezone.utc).isoformat(), "today": today.isoformat()}
    result["collection"] = collect_new_visitors(raw_dir, today) if collect else {"status": "skipped"}
    before = daily_service.model_status()
    latest = latest_raw_date(default_visitor_paths(raw_dir))
    result["before"] = {key: before.get(key) for key in ("status", "model_version", "data_end", "days_until_stale")}
    data_end = before.get("data_end")
    new_days = (latest - data_end).days if data_end else None
    result["latest_raw_date"] = latest.isoformat()
    result["new_days"] = new_days
    due = before["status"] != "ready" or (new_days or 0) >= min_new_days or (
        (before.get("days_until_stale") or 0) <= stale_margin_days and (new_days or 0) > 0)
    if not due or (new_days is not None and new_days <= 0):
        result["action"] = "none"
    else:
        if before["status"] in {"ready", "stale"} and data_end:
            result["forward_evaluation"] = _forward_evaluate(daily_service._directory(), data_end, today)
        output_dir = next_production_directory(output_root)
        result["training"] = train_daily_model(default_visitor_paths(raw_dir), output_dir)
        result["action"] = "retrained"
    after = daily_service.model_status()
    result["after"] = {key: after.get(key) for key in ("status", "model_version", "data_end", "days_until_stale",
                                                       "last_predictable_target_date")}
    return result


def exit_code(result: dict) -> int:
    """0 정상, 2 재학습했지만 미채택, 4 곧 노후(14일 이하)·노후·모델 없음."""
    after = result["after"]
    if after["status"] != "ready" or (after.get("days_until_stale") or 0) <= WARN_DAYS:
        return 4
    if result.get("training") and not result["training"]["model_adopted"]:
        return 2
    return 0


def append_log(output_root: Path, result: dict) -> Path:
    path = output_root / "model-refresh-log.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(result, ensure_ascii=False, default=str) + "\n")
    return path


def refresh_lock(output_root: Path):
    """동시에 두 번 실행되지 않게 하는 파일 잠금(cron 겹침 방지)."""
    path = output_root / ".model-refresh.lock"

    class Lock:
        def __enter__(self):
            try:
                self.fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError as exc:
                raise RuntimeError("다른 재학습 작업이 실행 중입니다. 남은 잠금 파일이 있으면 지우고 다시 실행하세요: " + str(path)) from exc
            os.write(self.fd, str(os.getpid()).encode())
            return self

        def __exit__(self, *_):
            os.close(self.fd)
            path.unlink(missing_ok=True)

    return Lock()
