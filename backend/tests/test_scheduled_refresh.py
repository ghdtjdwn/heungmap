from datetime import date

import pytest

from app.demand import refresh


def run(monkeypatch, tmp_path, *, latest, before, adopted=True):
    calls = {"train": 0, "forward": 0}
    statuses = iter([before, {**before, "status": "ready", "days_until_stale": 50, "data_end": latest} if adopted else before])
    monkeypatch.setattr(refresh.daily_service, "model_status", lambda: next(statuses))
    monkeypatch.setattr(refresh.daily_service, "_directory", lambda: tmp_path)
    monkeypatch.setattr(refresh, "latest_raw_date", lambda _paths: latest)
    monkeypatch.setattr(refresh, "default_visitor_paths", lambda *_: [])
    monkeypatch.setattr(refresh, "_forward_evaluate", lambda *_: calls.__setitem__("forward", calls["forward"] + 1) or {"ok": True})

    def train(_paths, output_dir):
        calls["train"] += 1
        return {"model_adopted": adopted, "output": str(output_dir)}

    monkeypatch.setattr(refresh, "train_daily_model", train)
    result = refresh.run_scheduled_refresh(raw_dir=tmp_path, output_root=tmp_path, today=date(2026, 9, 25), collect=False)
    return result, calls


def ready(data_end, days):
    return {"status": "ready", "model_version": "m", "data_end": data_end, "days_until_stale": days}


def test_few_new_days_and_fresh_model_do_nothing(monkeypatch, tmp_path):
    result, calls = run(monkeypatch, tmp_path, latest=date(2026, 8, 22), before=ready(date(2026, 8, 19), 40))
    assert result["action"] == "none" and calls == {"train": 0, "forward": 0} and result["new_days"] == 3


def test_a_week_of_new_data_evaluates_then_retrains(monkeypatch, tmp_path):
    result, calls = run(monkeypatch, tmp_path, latest=date(2026, 8, 26), before=ready(date(2026, 8, 19), 40))
    assert result["action"] == "retrained" and calls == {"train": 1, "forward": 1} and refresh.exit_code(result) == 0


def test_close_to_stale_retrains_with_any_new_day(monkeypatch, tmp_path):
    result, calls = run(monkeypatch, tmp_path, latest=date(2026, 8, 21), before=ready(date(2026, 8, 19), 10))
    assert result["action"] == "retrained" and calls["train"] == 1


def test_no_new_data_near_stale_warns_and_rejected_model_is_reported(monkeypatch, tmp_path):
    result, _ = run(monkeypatch, tmp_path, latest=date(2026, 8, 19), before=ready(date(2026, 8, 19), 10), adopted=False)
    assert result["action"] == "none" and refresh.exit_code(result) == 4
    rejected, _ = run(monkeypatch, tmp_path, latest=date(2026, 8, 30), before=ready(date(2026, 8, 19), 40), adopted=False)
    assert refresh.exit_code({**rejected, "after": {"status": "ready", "days_until_stale": 40}}) == 2


def test_lock_blocks_overlapping_runs_and_log_appends(tmp_path):
    with refresh.refresh_lock(tmp_path):
        with pytest.raises(RuntimeError):
            with refresh.refresh_lock(tmp_path):
                pass
    with refresh.refresh_lock(tmp_path):
        pass
    path = refresh.append_log(tmp_path, {"a": 1})
    refresh.append_log(tmp_path, {"a": 2})
    assert len(path.read_text().splitlines()) == 2
