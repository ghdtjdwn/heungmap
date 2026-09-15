import pandas as pd

from app.attendance.data import FEATURES, build_training_pairs, canonical_title, feature_values, normalize_province


def test_canonical_title_removes_year_and_edition_but_preserves_words():
    assert canonical_title("2025 제12회 춘천 막국수·닭갈비 축제") == canonical_title("춘천 막국수 닭갈비 축제")
    assert canonical_title("서울 드럼 페스티벌") != canonical_title("서울 뮤직 페스티벌")


def test_province_aliases_are_stable():
    assert normalize_province("01. 서울") == "서울"
    assert normalize_province("강원특별자치도") == "강원"


def test_adjacent_pair_is_exact_unique_and_features_are_finite():
    records = pd.DataFrame([
        {"plan_year": 2024, "province": "강원", "district": "춘천시", "title": "제1회 감자 축제",
         "title_key": canonical_title("제1회 감자 축제"), "festival_type": "지역특산물",
         "budget_million_krw": 100.0, "first_year": 2024, "month": 6, "duration_days": 2,
         "prior_attendance": 10_000.0, "measurement": "미제공"},
        {"plan_year": 2025, "province": "강원", "district": "춘천시", "title": "제2회 감자축제",
         "title_key": canonical_title("제2회 감자축제"), "festival_type": "지역특산물",
         "budget_million_krw": 120.0, "first_year": 2024, "month": 6, "duration_days": 2,
         "prior_attendance": 12_000.0, "measurement": "계측"},
    ])
    frame, audit = build_training_pairs(records)
    assert len(frame) == 1 and frame.iloc[0].target_attendance == 12_000
    assert audit["pairs_by_target_year"] == {"2024": 1}
    assert list(feature_values(records.iloc[0])) == FEATURES

