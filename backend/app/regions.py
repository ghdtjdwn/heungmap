"""2026-07-01 행정구역 개편 대응. 법정동 코드가 바뀐 지역의 이력과 TourAPI 지역 코드를 이어 준다.

- 광주광역시·전라남도 27개 시군구는 전남광주통합특별시(시도 코드 12)로 이름·경계 그대로 코드만 바뀌었다.
  2026-09-18 원본에서 옛 코드는 06-30, 새 코드는 07-01부터 관측되고, 전년 대비 증감률이 경계 전후로 평균 1.4%p만
  달라(최대 5.3%p) 같은 지역으로 이어 붙인다.
- 인천 중구·동구·서구는 영종구·제물포구·서해구·검단구로 나뉘고 합쳐져 경계가 달라졌다. 이어 붙이면 틀린 이력이
  되므로 새 구는 1년 이력이 쌓일 때까지 예측하지 않는다.
"""
from __future__ import annotations

REORGANIZED_ON = "2026-07-01"
UNIFIED_REGION = "12"  # 전남광주통합특별시
RENAMED_REGION_CODES = {
    "29110": "12210", "29140": "12240", "29155": "12270", "29170": "12300", "29200": "12330",
    "46110": "12110", "46130": "12130", "46150": "12150", "46170": "12170", "46230": "12190",
    "46710": "12710", "46720": "12720", "46730": "12730", "46770": "12740", "46780": "12750",
    "46790": "12760", "46800": "12770", "46810": "12780", "46820": "12790", "46830": "12800",
    "46840": "12810", "46860": "12820", "46870": "12830", "46880": "12840", "46890": "12850",
    "46900": "12860", "46910": "12870",
}
PREDECESSOR_CODES = {new: old for old, new in RENAMED_REGION_CODES.items()}
SPLIT_WITHOUT_HISTORY = {"28125": "제물포구", "28155": "영종구", "28275": "서해구", "28290": "검단구"}
RETIRED_SPLIT_CODES = {"28110": "중구", "28140": "동구", "28260": "서구"}
# 공통 계약의 TourAPI 지역 코드(광주 5, 전남 38) ← 옛 법정동 시도 코드
_PREDECESSOR_AREA = {"29": "5", "46": "38"}


def predecessor_code(code: str) -> str:
    """새 코드면 개편 전 코드, 아니면 그대로."""
    return PREDECESSOR_CODES.get(code, code)


def tour_area_for_legal_code(code: str | None) -> str | None:
    """전남광주통합특별시 시군구 코드를 공통 계약의 광주(5)·전남(38) 지역 코드로 바꾼다."""
    if not code or len(code) != 5 or code[:2] != UNIFIED_REGION:
        return None
    return _PREDECESSOR_AREA.get(predecessor_code(code)[:2])


def split_region_message(code: str | None) -> str | None:
    """경계가 바뀐 새 구·옛 구에 대한 안내. 해당 없으면 None."""
    if code in SPLIT_WITHOUT_HISTORY:
        return f"{SPLIT_WITHOUT_HISTORY[code]}는 2026년 7월 행정구역 개편으로 새로 생겨 비교할 1년 이력이 없어 예측하지 않습니다."
    if code in RETIRED_SPLIT_CODES:
        return f"인천 {RETIRED_SPLIT_CODES[code]}는 2026년 7월 행정구역 개편으로 나뉘어 최신 이력이 없습니다."
    return None
