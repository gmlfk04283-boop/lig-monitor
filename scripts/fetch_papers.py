"""
에이전트 1 (수집기) - fetch_papers.py

역할:
  OpenAlex API(https://openalex.org, 무료/키 불필요)를 이용해
  "laser-induced graphene" 관련 논문을 검색하고,
  journals_config.json에 등록된 IF>=8 저널에서 출판된 것만 걸러
  data/papers.json 에 누적 저장한다.

  이 스크립트는 매주 GitHub Actions에 의해 자동 실행된다.
  이미 저장된 논문(DOI 기준)은 건너뛰고 새로운 것만 추가한다.

사용법:
  python scripts/fetch_papers.py
"""

import json
import os
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "scripts", "journals_config.json")
DATA_PATH = os.path.join(BASE_DIR, "data", "papers.json")

OPENALEX_API = "https://api.openalex.org/works"
# OpenAlex는 email을 붙여주면 더 안정적인 "polite pool"로 요청을 처리해준다.
CONTACT_EMAIL = os.environ.get("CONTACT_EMAIL", "example@example.com")

# 매주 실행되므로 최근 N일치만 반복 조회 (최초 실행 시엔 더 넓게, 이후엔 좁게)
LOOKBACK_DAYS_FIRST_RUN = 365 * 3   # 최초 실행: 최근 3년치 백필
LOOKBACK_DAYS_REGULAR = 14          # 이후 실행: 최근 2주 (혹시 놓친 논문 대비 여유)


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_existing_papers():
    if os.path.exists(DATA_PATH):
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_papers(papers):
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(papers, f, ensure_ascii=False, indent=2)


def reconstruct_abstract(inverted_index):
    """OpenAlex는 초록을 inverted index(단어->위치 리스트) 형태로 준다. 원문으로 복원."""
    if not inverted_index:
        return ""
    positions = {}
    for word, idxs in inverted_index.items():
        for idx in idxs:
            positions[idx] = word
    if not positions:
        return ""
    max_idx = max(positions.keys())
    words = [positions.get(i, "") for i in range(max_idx + 1)]
    return " ".join(words)


def normalize_journal_name(name):
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


def fetch_openalex_page(query, from_date, cursor="*", per_page=50):
    params = {
        "search": query,
        "filter": f"from_publication_date:{from_date}",
        "per-page": str(per_page),
        "cursor": cursor,
        "mailto": CONTACT_EMAIL,
    }
    url = OPENALEX_API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "lig-monitor/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_all(query, from_date):
    """OpenAlex cursor 페이지네이션을 순회하며 전체 결과를 모은다."""
    results = []
    cursor = "*"
    while True:
        data = fetch_openalex_page(query, from_date, cursor=cursor)
        results.extend(data.get("results", []))
        cursor = data.get("meta", {}).get("next_cursor")
        if not cursor or not data.get("results"):
            break
        time.sleep(0.3)  # API 예의상 약간의 딜레이
    return results


def main():
    config = load_config()
    existing = load_existing_papers()
    existing_dois = {p["doi"] for p in existing if p.get("doi")}

    journal_lookup = {
        normalize_journal_name(j["name"]): j for j in config["journals"]
    }
    min_if = config.get("min_impact_factor", 8.0)

    first_run = len(existing) == 0
    lookback = LOOKBACK_DAYS_FIRST_RUN if first_run else LOOKBACK_DAYS_REGULAR
    from_date = (datetime.utcnow() - timedelta(days=lookback)).strftime("%Y-%m-%d")

    new_papers = []
    for keyword in config["search_keywords"]:
        print(f"[fetch] searching OpenAlex for: {keyword} (from {from_date})")
        try:
            works = fetch_all(keyword, from_date)
        except Exception as e:
            print(f"[fetch] ERROR while searching '{keyword}': {e}")
            continue

        for w in works:
            doi = (w.get("doi") or "").replace("https://doi.org/", "")
            if not doi or doi in existing_dois:
                continue

            source = (w.get("primary_location") or {}).get("source") or {}
            journal_name = source.get("display_name", "")
            norm_name = normalize_journal_name(journal_name)

            matched_journal = journal_lookup.get(norm_name)
            if not matched_journal:
                continue  # 관심 저널 목록에 없는 저널이면 스킵
            if matched_journal["impact_factor"] < min_if:
                continue

            title = w.get("title") or ""
            abstract = reconstruct_abstract(w.get("abstract_inverted_index"))
            if not title or not abstract:
                continue  # 제목/초록 없는 항목은 분류가 불가하므로 제외

            paper = {
                "doi": doi,
                "title": title,
                "abstract": abstract,
                "journal": journal_name,
                "impact_factor": matched_journal["impact_factor"],
                "published_date": w.get("publication_date"),
                "openalex_id": w.get("id"),
                "collected_at": datetime.utcnow().isoformat(),
                "theme": None,           # 에이전트 2가 채울 필드
                "theme_rationale": None  # 에이전트 2가 채울 필드
            }
            new_papers.append(paper)
            existing_dois.add(doi)

    all_papers = existing + new_papers
    save_papers(all_papers)
    print(f"[fetch] done. {len(new_papers)} new papers added. total={len(all_papers)}")


if __name__ == "__main__":
    main()
