# 보안 취약점 신고

흥할지도 코드나 배포(heungmap.vercel.app)에서 보안 문제를 발견하면 공개 이슈 대신
[GitHub 비공개 취약점 신고](https://github.com/ghdtjdwn/heungmap/security/advisories/new)로 알려 주세요.
재현 절차와 영향 범위를 적어 주시면 확인 후 답변합니다.

- API 키·`.env`·모델 artifact·수집 데이터는 Git에 넣지 않습니다. 실수로 올라온 것을 발견하면 같은 경로로 알려 주세요.
- 의존성 취약점은 Dependabot이 주 1회 확인하고, PR마다 백엔드 테스트와 프론트 빌드가 CI에서 실행됩니다.
