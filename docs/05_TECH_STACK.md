# 05. 기술 스택 & 폴더 구조 (제안 — 다음 세션에서 최종 확정)

> 팀이 초심자이므로 **러닝커브가 낮고 자료 많은 스택** 우선. 아래는 제안이며, 첫 세션에서 팀 상황(특히 프론트 경험/시간) 보고 확정.

## 추천 스택
| 영역 | 추천 | 이유 / 대안 |
|---|---|---|
| 언어(데이터/모델/백엔드) | **Python** | 데이터·ML·백엔드를 한 언어로 |
| 데이터 처리 | pandas, requests | 표 다루기·API 호출 |
| 예측 모델(Tier1) | **LightGBM**(or XGBoost), scikit-learn | 표 데이터에 강함·튜토리얼 풍부 |
| 설명가능성(Tier2) | **SHAP** | 예측 근거 시각화 |
| 백엔드 API | **FastAPI** | 파이썬이라 러닝커브 최소 |
| 프론트엔드 | **Next.js(React)** *또는* **Streamlit** | Next.js=포폴 가치↑(권장) / Streamlit=초고속 MVP·전부 파이썬(시간 급하면) |
| 지도 | **Kakao Map JS SDK** | 국내 주차/장소 표시에 적합(한국어) |
| LLM(Tier2 리포트) | **Claude API** (`claude-sonnet` 등) | 보완 피드백 생성 |
| 협업 | GitHub | 공개 저장소에서 branch와 pull request로 검토 |

### 프론트 선택 가이드
- **포폴 임팩트 우선** → Next.js + FastAPI (분리형). 심사 완성도·확장성에도 유리.
- **완성 확실성/시간 우선** → 우선 Streamlit로 Tier0 MVP 뽑고, 여유 되면 Next.js로 이관.
- 초심자 2인·8주라면 **"Tier0는 Streamlit로 빠르게 → 되면 Next.js"** 도 현실적 타협안.

## 제안 폴더 구조 (모노레포)
```
heungmap/
├─ README.md, CLAUDE.md, .gitignore, .env.example
├─ docs/                # 기획·규정·로드맵 (현재 폴더)
├─ data/
│  ├─ raw/              # API 원본 (gitignore)
│  └─ processed/        # train.csv 등 (gitignore)
├─ scripts/             # 데이터 수집·조립 스크립트 (스파이크/파이프라인)
├─ model/               # 학습·평가·추론 (Tier1~2)
├─ backend/             # FastAPI (예측 API 서빙)
└─ frontend/            # Next.js 또는 streamlit_app/
```
> 위 code 디렉터리는 **바이브코딩 시 생성**. 지금은 docs/data만 존재.

## 환경 셋업 메모 (첫 세션에서)
- Python 3.11+ 설치 확인 → `python -m venv .venv` → 활성화 → `pip install pandas requests lightgbm scikit-learn shap fastapi uvicorn python-dotenv`
- Node 20+ (Next.js 쓸 경우)
- Python 없거나 설치 번거로우면 **데이터 스파이크는 Google Colab**으로 먼저 시작 가능.
