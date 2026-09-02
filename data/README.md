# data/

데이터 저장 폴더. **원본·가공 데이터는 git에 커밋하지 않습니다**(용량·라이선스). `.gitignore` 처리됨.

- `raw/` — API에서 받은 원본(JSON/CSV). 수집 스크립트 출력.
- `processed/` — 조립·정제된 학습표(`train.csv` 등). 모델 입력.

데이터 생성 절차는 [`../docs/DATA_AND_APIS.md`](../docs/DATA_AND_APIS.md)를 참조하세요.

> 폴더 유지를 위해 `.gitkeep`을 두세요. 새 clone 후 필요 시:
> `mkdir -p data/raw data/processed`
