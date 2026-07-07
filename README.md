# LIG Monitor

레이저 유도 그래핀(Laser-Induced Graphene, LIG) 논문을 임팩트팩터 8 이상 저널에서
매주 자동으로 수집·분류하고, 저널별 연구 트렌드를 지식그래프와 리포트로 보여주는
자동화 시스템입니다.

## 구조

```
lig-monitor/
├── .github/workflows/weekly_update.yml   # 매주 월요일 자동 실행(+수동 실행)
├── scripts/
│   ├── journals_config.json              # 감시 저널 목록, IF 기준, 테마 정의
│   ├── fetch_papers.py                   # 에이전트 1: 신규 논문 수집 (OpenAlex API)
│   └── analyze_papers.py                 # 에이전트 2: 테마 분류 + 리포트/그래프 생성 (Claude API)
├── data/
│   ├── papers.json                       # 누적 논문 데이터 (공유 "빅데이터")
│   ├── journal_theme_graph.json          # 웹사이트가 그리는 지식그래프 데이터
│   └── reports/YYYY-MM-DD.md             # 주차별 리포트
└── site/                                 # GitHub Pages로 배포되는 대시보드 웹사이트
```

## 설치 방법 (최초 1회, 약 15분)

1. **저장소 만들기**
   - GitHub에서 새 저장소를 만들고 (예: `lig-monitor`), 이 폴더의 내용을 그대로 업로드/푸시합니다.

2. **OpenAI API 키 준비**
   - 이미 가지고 계신 OpenAI API 키를 그대로 사용하시면 됩니다 (https://platform.openai.com/api-keys 에서 확인/재발급 가능).

3. **GitHub Secrets 등록**
   - 저장소 → Settings → Secrets and variables → Actions → New repository secret
   - `OPENAI_API_KEY` : 보유하신 OpenAI API 키
   - `CONTACT_EMAIL` : 본인 이메일 (OpenAlex API가 안정적으로 응답하도록 사용, 없어도 동작하지만 등록 권장)

4. **GitHub Pages 활성화**
   - 저장소 → Settings → Pages → Build and deployment → Source를 **"GitHub Actions"** 로 선택합니다.
   - (Deploy from a branch 방식이 아니라 반드시 "GitHub Actions" 방식이어야 합니다. workflow가 site/ 폴더를 직접 배포하도록 만들어져 있습니다.)

5. **첫 실행**
   - 저장소 → Actions 탭 → "Weekly LIG paper monitor" → Run workflow 버튼으로 수동 실행합니다.
   - 첫 실행은 최근 3년치 논문을 백필하므로 몇 분 정도 걸릴 수 있습니다.
   - 완료되면 Settings → Pages에 표시된 URL로 접속하면 대시보드가 보입니다.

이후에는 매주 월요일 00:00 UTC(한국시간 오전 9시)에 자동으로:
1. 신규 LIG 논문 수집 → 2. Claude로 테마 분류 → 3. 지식그래프/리포트 갱신 → 4. 웹사이트 자동 재배포

가 반복됩니다.

## 저널/테마 커스터마이징

- `scripts/journals_config.json`의 `journals` 배열에 저널을 추가/삭제하거나 `impact_factor` 값을 최신 JCR 기준으로 갱신하세요.
- `themes` 배열을 수정하면 분류 기준 자체를 바꿀 수 있습니다 (예: "응용분야별"이 아니라 "제조공정별"로 재정의 등).
- 검색 키워드(`search_keywords`)에 관심 있는 하위 주제를 추가할 수 있습니다 (예: `"laser-induced graphene sensor"`).

## 반도체/능동소자 경쟁 동향 알림

일반 테마 분류와 별도로, 에이전트 2는 논문마다 아래 세 카테고리(`scripts/journals_config.json`의
`semiconductor_categories`)에도 해당하는지 다중 분류합니다:

- **doping** — 도핑/원소 기능화
- **wafer_scale_synthesis** — 웨이퍼 기반/반도체 공정 호환 합성
- **active_device** — 능동소자 응용 (트랜지스터, 다이오드, 광검출기 등)

해당되는 논문이 감지되면:
1. `data/semiconductor_alerts.json` 에 누적 저장되고, 대시보드 맨 위 "⚠ 반도체/능동소자 관련 논문" 패널에 표시됩니다.
2. 그 주의 리포트(`data/reports/YYYY-MM-DD.md`)에 "⚠ 반도체/능동소자 관련 논문 감지" 섹션이 별도로 생성됩니다.

카테고리 정의(`description`)를 더 구체적으로 다듬을수록 분류 정확도가 올라갑니다.
연구 방향이 바뀌면 `journals_config.json`의 `semiconductor_categories`만 수정하면 됩니다
(예: "n형 도핑"과 "p형 도핑"을 별도 카테고리로 나누는 등).

## 로컬에서 테스트하기

```bash
pip install -r requirements.txt
export OPENAI_API_KEY=sk-...
export CONTACT_EMAIL=you@example.com
python scripts/fetch_papers.py
python scripts/analyze_papers.py
```

`site/index.html`을 로컬 서버로 열어 확인하려면 (fetch가 파일:// 프로토콜에서 막히므로 서버 필요):

```bash
cd site
cp -r ../data ./data
python -m http.server 8000
# http://localhost:8000 접속
```

## 알아둘 점

- IF(임팩트팩터) 값은 매년 6월경 갱신됩니다. `journals_config.json`의 값은 참고용 근사치이니 주기적으로 확인해 주세요.
- OpenAlex는 논문의 제목/초록/저널명/출판일 정도만 제공하며, 본문 전체 텍스트는 제공하지 않습니다. 더 정교한 분석이 필요하면 각 논문의 DOI 링크를 통해 원문을 직접 확인하세요.
- 논문 수가 많아지면 OpenAI API 호출 비용이 늘어날 수 있습니다 (초록 1건당 매우 저렴하지만, 누적 시 확인 필요). 기본 모델은 `gpt-4o-mini`로 설정해뒀고, 다른 모델을 쓰고 싶으면 워크플로우 파일의 env에 `OPENAI_MODEL` 값을 추가하면 됩니다.
