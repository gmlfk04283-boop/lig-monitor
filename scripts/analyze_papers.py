"""
에이전트 2 (분석기) - analyze_papers.py

역할:
  data/papers.json 에서 아직 분류(theme)되지 않은 논문을 찾아
  Claude API로 어떤 연구 테마(신규 응용/성능최적화/에너지저장/메커니즘/리뷰)에
  해당하는지 분류한다.

  분류가 끝나면:
    1) data/journal_theme_graph.json  - 저널 x 테마 지식그래프 데이터(웹사이트가 읽음)
    2) data/reports/<날짜>.md         - 이번 실행 시점 기준 주간 리포트

  환경변수 ANTHROPIC_API_KEY 가 필요하다 (GitHub Secrets에 등록).

사용법:
  python scripts/analyze_papers.py
"""

import json
import os
from collections import defaultdict
from datetime import datetime

from openai import OpenAI

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "scripts", "journals_config.json")
PAPERS_PATH = os.path.join(BASE_DIR, "data", "papers.json")
GRAPH_PATH = os.path.join(BASE_DIR, "data", "journal_theme_graph.json")
ALERTS_PATH = os.path.join(BASE_DIR, "data", "semiconductor_alerts.json")
REPORTS_DIR = os.path.join(BASE_DIR, "data", "reports")

# 사용할 OpenAI 모델. 환경변수로 바꿀 수 있게 해뒀으니, 계정에서 사용 가능한
# 다른 모델(예: "gpt-4o", "gpt-5-mini" 등)로 교체하고 싶으면
# GitHub Secrets 대신 워크플로우의 env에 OPENAI_MODEL 값을 추가하면 됩니다.
MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

client = OpenAI()  # OPENAI_API_KEY 환경변수를 자동으로 읽음


def load_json(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def classify_paper(paper, themes, semiconductor_categories):
    theme_list_str = "\n".join(
        f"- {t['id']}: {t['label_ko']} — {t['description']}" for t in themes
    )
    semi_list_str = "\n".join(
        f"- {c['id']}: {c['label_ko']} — {c['description']}" for c in semiconductor_categories
    )
    prompt = f"""당신은 레이저 유도 그래핀(Laser-Induced Graphene, LIG) 분야 논문을 분류하는 전문가입니다.
아래 논문의 제목과 초록을 읽고 두 가지를 분류하세요.

[분류 1] 이 저널이 LIG를 어떤 관점에서 다루는지, 아래 테마 중 가장 적합한 것 하나를 선택:
{theme_list_str}

[분류 2] 이 논문이 "LIG의 반도체 소자화" 연구와 겹치는지 판단. 아래 카테고리 중 해당하는 것을
0개 이상 모두 선택 (해당 없으면 빈 배열). 단순히 전극/배선/센서용 도체로 LIG를 쓰는 논문은
해당 없음으로 처리하고, 아래 정의에 명시적으로 부합할 때만 선택하세요:
{semi_list_str}

논문 제목: {paper['title']}
논문 초록: {paper['abstract']}

반드시 아래 JSON 형식으로만 답하세요. 다른 설명은 절대 추가하지 마세요.
{{
  "theme_id": "선택한 테마 id",
  "rationale_ko": "이 논문이 왜 이 테마에 해당하는지 한국어 1문장 설명",
  "application_keywords": ["핵심 응용 키워드 2~4개"],
  "semiconductor_categories": ["해당하는 카테고리 id들, 없으면 빈 배열"],
  "semiconductor_rationale_ko": "반도체 소자 관련이라고 판단한 한국어 1문장 근거 (해당 없으면 빈 문자열)"
}}"""

    resp = client.chat.completions.create(
        model=MODEL,
        max_tokens=400,
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": prompt}],
    )
    text = resp.choices[0].message.content.strip()
    return json.loads(text)


def build_graph(papers, themes):
    """저널 x 테마 카운트를 집계해 지식그래프용 노드/엣지 데이터를 만든다."""
    theme_meta = {t["id"]: t for t in themes}
    edge_counts = defaultdict(int)
    journal_totals = defaultdict(int)
    theme_totals = defaultdict(int)

    for p in papers:
        if not p.get("theme"):
            continue
        edge_counts[(p["journal"], p["theme"])] += 1
        journal_totals[p["journal"]] += 1
        theme_totals[p["theme"]] += 1

    nodes = []
    for j, total in journal_totals.items():
        nodes.append({"id": j, "type": "journal", "count": total})
    for t_id, total in theme_totals.items():
        label = theme_meta.get(t_id, {}).get("label_ko", t_id)
        nodes.append({"id": t_id, "type": "theme", "label": label, "count": total})

    edges = [
        {"source": j, "target": t, "weight": c}
        for (j, t), c in edge_counts.items()
    ]

    return {
        "generated_at": datetime.utcnow().isoformat(),
        "nodes": nodes,
        "edges": edges,
    }


def build_semiconductor_alerts(papers, semiconductor_categories):
    """반도체 소자 관련으로 분류된 논문만 모아 별도 알림 데이터셋을 만든다."""
    cat_meta = {c["id"]: c["label_ko"] for c in semiconductor_categories}
    alerts = []
    for p in papers:
        cats = p.get("semiconductor_categories") or []
        if not cats:
            continue
        alerts.append({
            "doi": p["doi"],
            "title": p["title"],
            "journal": p["journal"],
            "impact_factor": p["impact_factor"],
            "published_date": p.get("published_date"),
            "categories": cats,
            "category_labels": [cat_meta.get(c, c) for c in cats],
            "rationale_ko": p.get("semiconductor_rationale"),
        })
    alerts.sort(key=lambda x: x.get("published_date") or "", reverse=True)
    return {
        "generated_at": datetime.utcnow().isoformat(),
        "total": len(alerts),
        "alerts": alerts,
    }


def build_weekly_report(papers, themes, new_papers, semiconductor_categories):
    theme_meta = {t["id"]: t["label_ko"] for t in themes}
    cat_meta = {c["id"]: c["label_ko"] for c in semiconductor_categories}
    lines = []
    lines.append(f"# LIG 논문 주간 리포트 ({datetime.utcnow().strftime('%Y-%m-%d')})")
    lines.append("")
    lines.append(f"이번 주기 신규 수집 논문: **{len(new_papers)}건**")
    lines.append("")

    new_semi_hits = [p for p in new_papers if p.get("semiconductor_categories")]
    if new_semi_hits:
        lines.append("## ⚠ 반도체/능동소자 관련 논문 감지 (경쟁 동향 알림)")
        lines.append("")
        lines.append("우리 연구(도핑, 웨이퍼 기반 합성, 능동소자 응용)와 겹칠 수 있는 신규 논문입니다.")
        lines.append("")
        for p in new_semi_hits:
            cats = ", ".join(cat_meta.get(c, c) for c in p["semiconductor_categories"])
            lines.append(
                f"- **[{p['journal']} (IF {p['impact_factor']})]** {p['title']} "
                f"— https://doi.org/{p['doi']}"
            )
            lines.append(f"  - 해당 카테고리: {cats}")
            if p.get("semiconductor_rationale"):
                lines.append(f"  - 판단 근거: {p['semiconductor_rationale']}")
        lines.append("")

    if new_papers:
        lines.append("## 신규 논문 목록 (전체)")
        for p in sorted(new_papers, key=lambda x: x.get("impact_factor", 0), reverse=True):
            theme_label = theme_meta.get(p.get("theme"), "미분류")
            flag = " ⚠" if p.get("semiconductor_categories") else ""
            lines.append(
                f"- **[{p['journal']} (IF {p['impact_factor']})]** {p['title']}{flag} "
                f"— 테마: {theme_label}"
            )
            if p.get("theme_rationale"):
                lines.append(f"  - 분류 근거: {p['theme_rationale']}")
        lines.append("")

    lines.append("## 저널별 누적 테마 분포")
    by_journal = defaultdict(lambda: defaultdict(int))
    for p in papers:
        if p.get("theme"):
            by_journal[p["journal"]][p["theme"]] += 1

    for journal, counts in sorted(by_journal.items()):
        total = sum(counts.values())
        lines.append(f"### {journal} (누적 {total}건)")
        for theme_id, cnt in sorted(counts.items(), key=lambda x: -x[1]):
            label = theme_meta.get(theme_id, theme_id)
            pct = round(100 * cnt / total)
            lines.append(f"- {label}: {cnt}건 ({pct}%)")
        lines.append("")

    total_semi = sum(1 for p in papers if p.get("semiconductor_categories"))
    if total_semi:
        lines.append("## 누적 반도체/능동소자 관련 논문 현황")
        lines.append(f"지금까지 총 **{total_semi}건**이 감지되었습니다.")
        cat_counts = defaultdict(int)
        for p in papers:
            for c in (p.get("semiconductor_categories") or []):
                cat_counts[c] += 1
        for c, cnt in sorted(cat_counts.items(), key=lambda x: -x[1]):
            lines.append(f"- {cat_meta.get(c, c)}: {cnt}건")
        lines.append("")

    return "\n".join(lines)


def main():
    config = load_json(CONFIG_PATH, {})
    themes = config.get("themes", [])
    semiconductor_categories = config.get("semiconductor_categories", [])
    papers = load_json(PAPERS_PATH, [])

    unclassified = [p for p in papers if not p.get("theme")]
    print(f"[analyze] {len(unclassified)} papers to classify")

    newly_classified = []
    for p in unclassified:
        try:
            result = classify_paper(p, themes, semiconductor_categories)
            p["theme"] = result.get("theme_id")
            p["theme_rationale"] = result.get("rationale_ko")
            p["application_keywords"] = result.get("application_keywords", [])
            p["semiconductor_categories"] = result.get("semiconductor_categories", [])
            p["semiconductor_rationale"] = result.get("semiconductor_rationale_ko", "")
            newly_classified.append(p)
            flag = " [SEMI]" if p["semiconductor_categories"] else ""
            print(f"  - classified: {p['title'][:50]}... -> {p['theme']}{flag}")
        except Exception as e:
            print(f"  - ERROR classifying '{p['title'][:50]}': {e}")

    save_json(PAPERS_PATH, papers)

    graph = build_graph(papers, themes)
    save_json(GRAPH_PATH, graph)

    alerts = build_semiconductor_alerts(papers, semiconductor_categories)
    save_json(ALERTS_PATH, alerts)

    report_md = build_weekly_report(papers, themes, newly_classified, semiconductor_categories)
    os.makedirs(REPORTS_DIR, exist_ok=True)
    report_filename = f"{datetime.utcnow().strftime('%Y-%m-%d')}.md"
    with open(os.path.join(REPORTS_DIR, report_filename), "w", encoding="utf-8") as f:
        f.write(report_md)

    # 최신 리포트 목록 인덱스 갱신 (웹사이트가 이 파일로 리포트 리스트를 불러옴)
    reports_index = sorted(
        [f for f in os.listdir(REPORTS_DIR) if f.endswith(".md")], reverse=True
    )
    save_json(os.path.join(REPORTS_DIR, "index.json"), reports_index)

    new_semi_count = sum(1 for p in newly_classified if p.get("semiconductor_categories"))
    print(
        f"[analyze] done. report saved -> data/reports/{report_filename} "
        f"({new_semi_count} new semiconductor-relevant papers flagged)"
    )


if __name__ == "__main__":
    main()
