# 기술 스택과 폴더 구조

현재 기술 스택은 데이터 검증 결과와 사용자 흐름에 따라 확정할 후보입니다. 재현성, 운영 복잡도와
유지보수 비용을 우선합니다.

## 기술 후보

| 영역 | 후보 | 선택 기준 |
| --- | --- | --- |
| 데이터·모델·API 언어 | Python | 수집, 학습과 serving을 같은 생태계에서 유지 |
| 데이터 처리 | pandas, requests | 표 형식 조립과 HTTP 수집 |
| 예측 모델 | LightGBM 또는 XGBoost, scikit-learn | 표 데이터 baseline 대비 검증 결과 |
| 모델 설명 | SHAP | 개별 예측의 영향 요인 표시 |
| backend API | FastAPI | Python 추론 코드와의 통합, schema 검증 |
| frontend | Next.js 또는 Streamlit | 사용자 화면 요구와 운영 비용으로 결정 |
| 지도 | Kakao Map JavaScript SDK | 국내 위치·주차·숙소 표현 |
| 설명 생성 | 공급자 중립 LLM API | 선택 기능으로 격리하고 timeout·fallback 제공 |
| 협업 | GitHub | branch와 pull request 기반 검토 |

### frontend 선택 기준

- Next.js와 FastAPI 분리형은 사용자 화면의 확장성과 API 경계를 우선할 때 사용합니다.
- Streamlit 단일 앱은 데이터와 사용자 흐름을 빠르게 검증할 때 사용합니다.
- 어떤 선택에서도 데이터 수집·학습 코드와 화면 코드를 분리해 frontend 교체 비용을 제한합니다.

## 목표 폴더 구조

```text
heungmap/
├─ README.md, .gitignore, .env.example
├─ docs/                # 제품·데이터·기술 명세
├─ data/
│  ├─ raw/              # API 원본, Git 제외
│  └─ processed/        # 학습표, Git 제외
├─ scripts/             # 데이터 수집·조립
├─ model/               # 학습·평가·추론
├─ backend/             # FastAPI
└─ frontend/            # Next.js 또는 Streamlit
```

코드 디렉터리는 해당 단계가 시작될 때 생성합니다. 현재 저장소에는 문서와 데이터 경로만 있습니다.

## 로컬 환경 기준

- Python 3.11 이상과 가상 환경
- 데이터 단계: pandas, requests, python-dotenv
- 모델 단계: lightgbm 또는 xgboost, scikit-learn, shap
- API 단계: fastapi, uvicorn
- Next.js 선택 시 Node.js 20 이상

실제 의존성은 사용하는 단계에 맞춰 lockfile에 고정하고, 설치와 검증 명령을 README에 추가합니다.
