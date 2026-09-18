"""일별 모델 학습·평가에 쓰는 원본 파일 목록을 한곳에서 정한다."""
from __future__ import annotations

from pathlib import Path

RAW_DIRECTORY = Path(__file__).resolve().parents[3] / "data" / "raw"
# visitors.jsonl·visitors-2025.jsonl은 같은 기간의 이전 부분 수집본이라 제외한다.
BASE_VISITOR_FILES = ("visitors-2025-full.jsonl", "visitors-2026-jan-aug.jsonl")
FESTIVAL_FILES = ("festivals-2024.jsonl", "festivals-2025.jsonl", "festivals-2026-jan-aug.jsonl")


def default_visitor_paths(raw_directory: Path = RAW_DIRECTORY) -> list[Path]:
    """기본 원본과 append-only 갱신 파일(`visitors-*-refresh-*.jsonl`)을 수집일 순서로 돌려준다."""
    refreshes = sorted(raw_directory.glob("visitors-*-refresh-*.jsonl"), key=lambda path: (path.stem.rsplit("-", 1)[-1], path.name))
    return [raw_directory / name for name in BASE_VISITOR_FILES] + refreshes


def default_festival_paths(raw_directory: Path = RAW_DIRECTORY) -> list[Path]:
    return [raw_directory / name for name in FESTIVAL_FILES]
