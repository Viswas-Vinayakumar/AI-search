"""Grade every search method against the golden set, and test the query parser.

Run:  python evaluate.py
Writes the tables to results/results.md (paste them into the README).
"""
import json
import math
from pathlib import Path

import pandas as pd

from search import BY_ID, DATA, METHODS, parse_query

ROOT = Path(__file__).parent
GOLDEN = [json.loads(line) for line in (DATA / "golden.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]

# A coach with grade 2 is a "must-find" (perfect) match; grade 1 is "partly right".
# Recall@5 and MRR@10 count only must-find coaches. nDCG@5 uses both grades.


# ----------------------------- grading -----------------------------
def recall_at(ranked, must_find, k=5):
    return len(set(ranked[:k]) & must_find) / len(must_find)


def reciprocal_rank(ranked, must_find, cutoff=10):
    for pos, cid in enumerate(ranked[:cutoff], start=1):
        if cid in must_find:
            return 1 / pos, pos
    return 0.0, None


def ndcg_at(ranked, grades, k=5):
    dcg = sum(grades.get(cid, 0) / math.log2(pos + 1) for pos, cid in enumerate(ranked[:k], start=1))
    ideal = sorted(grades.values(), reverse=True)[:k]
    idcg = sum(g / math.log2(pos + 1) for pos, g in enumerate(ideal, start=1))
    return dcg / idcg


def evaluate():
    rows = []
    for g in GOLDEN:
        grades = g["relevant"]
        must_find = {cid for cid, grade in grades.items() if grade == 2}
        row = {"query": g["query"], "query_en": g["query_en"], "tests": g["tests"]}
        for name, fn in METHODS.items():
            ranked = [cid for cid, _ in fn(g["query"], g.get("filters", {}))]    # the search sees ONLY the query
            rr, pos = reciprocal_rank(ranked, must_find)                          # grading starts here
            row[f"{name}|recall5"] = recall_at(ranked, must_find)
            row[f"{name}|rr"] = rr
            row[f"{name}|ndcg5"] = ndcg_at(ranked, grades)
            row[f"{name}|rank"] = pos
            row[f"{name}|top3"] = ranked[:3]
        rows.append(row)
    res = pd.DataFrame(rows)
    summary = pd.DataFrame({
        name: {"Recall@5": res[f"{name}|recall5"].mean(),
               "MRR@10": res[f"{name}|rr"].mean(),
               "nDCG@5": res[f"{name}|ndcg5"].mean()}
        for name in METHODS
    }).T.round(2)
    return res, summary


# ----------------------- query-parser tests -----------------------
PARSER_TESTS = [
    ("Konfliktlösung für unser Vertriebsteam in Hamburg, vor Ort, max. 2.000 €",
     {"city": "Hamburg", "format": "onsite", "max_price": 2000}),
    ("Präsentationstraining in München bis 1500 Euro", {"city": "München", "max_price": 1500}),
    ("Burnout Prävention online", {"format": "online"}),
    ("Teamcoaching für Remote-Teams", {}),                       # trap: "Remote" here is a topic, not a format
    ("Scrum Einführung, Budget 1.200 €", {"max_price": 1200}),
    ("Datenschutz Schulung Köln", {"city": "Köln"}),
    ("Einarbeitung neuer Kollegen, 900 €, virtuell", {"max_price": 900, "format": "online"}),
    ("die ersten 100 Tage als Führungskraft", {}),               # trap: 100 is not a price
]


def test_parser():
    lines, passed = [], 0
    for text, expected in PARSER_TESTS:
        clean, got = parse_query(text)
        ok = got == expected
        passed += ok
        lines.append(f"| {'✅' if ok else '❌'} | {text} | `{got}` | {clean} |")
    return passed, lines


# ----------------------------- report -----------------------------
def fmt_rank(r):
    return "–" if r is None or (isinstance(r, float) and math.isnan(r)) else f"#{int(r)}"


def main():
    res, summary = evaluate()
    passed, parser_lines = test_parser()
    names = list(METHODS)

    out = ["## Results (15 queries, 30 synthetic coaches)", "",
           "| Method | Recall@5 | MRR@10 | nDCG@5 |", "|---|---|---|---|"]
    out += [f"| {n} | {r['Recall@5']:.2f} | {r['MRR@10']:.2f} | {r['nDCG@5']:.2f} |" for n, r in summary.iterrows()]
    out += ["", "## Position of the first must-find coach (– = not in the top 10)", "",
            "| Query | English | " + " | ".join(names) + " |", "|---|---|" + "---|" * len(names)]
    for _, r in res.iterrows():
        out.append(f"| {r['query']} | {r['query_en']} | " + " | ".join(fmt_rank(r[f'{n}|rank']) for n in names) + " |")
    out += ["", f"## Query understanding: {passed}/{len(PARSER_TESTS)} parser tests passed", "",
            "| | Input | Extracted filters | Remaining query |", "|---|---|---|---|"] + parser_lines
    report = "\n".join(out)

    print(report)
    print("\n## Error analysis: queries where a method missed #1\n")
    for _, r in res.iterrows():
        misses = [n for n in names if r[f"{n}|rank"] != 1]
        if not misses:
            continue
        print(f"- {r['query']}  ({r['query_en']}) — tests: {r['tests']}")
        for n in misses:
            top = ", ".join(f"{c} {BY_ID[c]['title_en']}" for c in r[f"{n}|top3"]) or "nothing found"
            print(f"    {n:<13} {fmt_rank(r[f'{n}|rank']):>3}  top 3: {top}")

    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results" / "results.md").write_text(report + "\n", encoding="utf-8")
    res.drop(columns=[c for c in res.columns if c.endswith("|top3")]).to_csv(ROOT / "results" / "per_query.csv", index=False)


if __name__ == "__main__":
    main()
