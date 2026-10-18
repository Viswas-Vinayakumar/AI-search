"""Coach search: query understanding, keyword (BM25), semantic (embeddings), chunking, hybrid (RRF).

Everything the demo (app.py) and the evaluation (evaluate.py) use lives here,
so both always run exactly the same search.
"""
import json
import math
import re
from pathlib import Path

import numpy as np

DATA = Path(__file__).parent / "data"
COACHES = json.loads((DATA / "coaches.json").read_text(encoding="utf-8"))
BY_ID = {c["id"]: c for c in COACHES}
IDS = [c["id"] for c in COACHES]


def doc_text(c):
    return f"{c['title']}. {c['bio']}"


# =====================================================================
# 1. QUERY UNDERSTANDING: pull hard filters (city, budget, format) out of free text
#    Rules, not a model: numbers and places must be exact, and rules are easy to test.
# =====================================================================
CITIES = sorted({c["city"] for c in COACHES if c["city"] != "Online"})
NUMBER = r"(\d{1,3}(?:[.\s]\d{3})+|\d+)"                     # 2.000 / 2 000 / 2000
BUDGET_PATTERNS = [
    rf"(?:max(?:imal)?\.?|bis(?:\s+zu)?|höchstens|unter|budget:?)\s*{NUMBER}\s*(?:€|euro\b|eur\b)?",
    rf"{NUMBER}\s*(?:€|euro\b|eur\b)",
]
ONLINE = r"\b(?:online|virtuell)\b(?!-)"                     # "Remote-Teams" is a topic, not a format
ONSITE = r"\bvor\s+ort\b|\bin\s+präsenz\b"


def parse_query(text):
    """'Konfliktlösung in Hamburg, vor Ort, max. 2.000 €' ->
    ('Konfliktlösung', {'city': 'Hamburg', 'format': 'onsite', 'max_price': 2000})"""
    filters, clean = {}, text
    for city in CITIES:
        m = re.search(rf"\b(?:in\s+)?{city}\b", clean, re.I)
        if m:
            filters["city"] = city
            clean = clean[:m.start()] + clean[m.end():]
            break
    for pattern in BUDGET_PATTERNS:
        m = re.search(pattern, clean, re.I)
        if m:
            filters["max_price"] = int(re.sub(r"[.\s]", "", m.group(1)))
            clean = clean[:m.start()] + clean[m.end():]
            break
    for fmt, pattern in (("online", ONLINE), ("onsite", ONSITE)):
        m = re.search(pattern, clean, re.I)
        if m:
            filters["format"] = fmt
            clean = clean[:m.start()] + clean[m.end():]
            break
    clean = re.sub(r"\s*,\s*(,\s*)*", ", ", clean)               # tidy leftover commas
    clean = re.sub(r"\s+", " ", clean).strip(" ,.;")
    return clean, filters


def allowed(c, filters):
    """Hard rules, never left to a model."""
    if filters.get("city") and c["city"] != filters["city"]:
        return False
    if filters.get("max_price") and c["price"] > filters["max_price"]:
        return False
    if filters.get("format") == "online" and c["city"] != "Online":
        return False
    if filters.get("format") == "onsite" and c["city"] == "Online":
        return False
    return True


# =====================================================================
# 2. KEYWORD SEARCH: BM25, written out (same formula as the lesson)
# =====================================================================
STOPWORDS = {
    "für", "und", "der", "die", "das", "den", "dem", "des", "ein", "eine", "einen", "einem", "einer",
    "unser", "unsere", "unseren", "mit", "im", "in", "auf", "zu", "zum", "zur", "von", "vom", "bei",
    "als", "an", "am", "wie", "ich", "wir", "es", "ist", "sind", "haben", "hat", "wenn", "nicht",
    "oder", "aber", "auch", "sich", "über", "ganze", "the", "a", "for", "and", "of", "to",
}
K1, B = 1.5, 0.75


def tokenize(text):
    return [w for w in re.findall(r"\w+", text.lower()) if w not in STOPWORDS]


DOC_TOKENS = {c["id"]: tokenize(doc_text(c)) for c in COACHES}
AVG_LEN = sum(len(t) for t in DOC_TOKENS.values()) / len(DOC_TOKENS)
DOC_FREQ = {}
for toks in DOC_TOKENS.values():
    for w in set(toks):
        DOC_FREQ[w] = DOC_FREQ.get(w, 0) + 1


def idf(word):
    n = DOC_FREQ.get(word, 0)
    return math.log(1 + (len(IDS) - n + 0.5) / (n + 0.5))


def bm25(query, cid):
    doc, score = DOC_TOKENS[cid], 0.0
    for w in tokenize(query):
        tf = doc.count(w)
        if tf:
            score += idf(w) * tf * (K1 + 1) / (tf + K1 * (1 - B + B * len(doc) / AVG_LEN))
    return score


def keyword_rank(query, filters=None):
    filters = filters or {}
    scored = [(cid, bm25(query, cid)) for cid in IDS if allowed(BY_ID[cid], filters)]
    return sorted([x for x in scored if x[1] > 0], key=lambda x: -x[1])   # 0 = no shared word


# =====================================================================
# 3. SEMANTIC SEARCH: multilingual sentence embeddings + cosine similarity
# =====================================================================
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
_model, _doc_vecs, _chunk_vecs = None, None, None


def embed(texts):
    """Text(s) -> length-1 vectors. Loads the model once, on first use."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(MODEL_NAME)
    return np.asarray(_model.encode(list(texts), normalize_embeddings=True))


def doc_vectors():
    global _doc_vecs
    if _doc_vecs is None:
        _doc_vecs = embed(doc_text(c) for c in COACHES)        # whole profile -> one vector (mean pooling)
    return _doc_vecs


def vector_rank(query, filters=None):
    filters = filters or {}
    scores = doc_vectors() @ embed([query])[0]                  # cosine similarity
    ranked = sorted(zip(IDS, scores.tolist()), key=lambda x: -x[1])
    return [(cid, s) for cid, s in ranked if allowed(BY_ID[cid], filters)]


# =====================================================================
# 4. CHUNKING: score each profile by its BEST-matching piece (fixes dilution)
# =====================================================================
def chunks(c):
    """Title + each sentence / comma part of the bio. 1-word bits are glued to the previous piece."""
    pieces = []
    for part in re.split(r"[.:;,]", c["bio"]):
        part = part.strip()
        if not part:
            continue
        if len(part.split()) < 2 and pieces:
            pieces[-1] = f"{pieces[-1]}, {part}"
        else:
            pieces.append(part)
    return [c["title"]] + pieces


CHUNKS = {c["id"]: chunks(c) for c in COACHES}


def chunk_vectors():
    global _chunk_vecs
    if _chunk_vecs is None:
        _chunk_vecs = {cid: embed(CHUNKS[cid]) for cid in IDS}
    return _chunk_vecs


def best_chunk(query_vec, cid):
    sims = chunk_vectors()[cid] @ query_vec
    i = int(np.argmax(sims))
    return float(sims[i]), CHUNKS[cid][i]


def chunk_rank(query, filters=None):
    filters = filters or {}
    q = embed([query])[0]
    scored = [(cid, best_chunk(q, cid)[0]) for cid in IDS if allowed(BY_ID[cid], filters)]
    return sorted(scored, key=lambda x: -x[1])


# =====================================================================
# 5. HYBRID: Reciprocal Rank Fusion of keyword + semantic ranks
# =====================================================================
def rrf(*rankings, k=60):
    fused = {}
    for ranking in rankings:
        for rank, (cid, _) in enumerate(ranking, start=1):
            fused[cid] = fused.get(cid, 0.0) + 1 / (k + rank)
    return sorted(fused.items(), key=lambda x: -x[1])


def hybrid_rank(query, filters=None):
    return rrf(keyword_rank(query, filters), vector_rank(query, filters))


def hybrid_chunk_rank(query, filters=None):
    return rrf(keyword_rank(query, filters), chunk_rank(query, filters))


METHODS = {
    "keyword": keyword_rank,
    "vector": vector_rank,
    "vector_chunk": chunk_rank,
    "hybrid": hybrid_rank,
    "hybrid_chunk": hybrid_chunk_rank,
}


# =====================================================================
# 6. ONE CALL FOR THE DEMO: understand -> search -> explain
# =====================================================================
def search(text, method="hybrid_chunk", top=5):
    clean, filters = parse_query(text)
    query = clean or text
    ranked = METHODS[method](query, filters)[:top]
    q = embed([query])[0]
    results = []
    for cid, score in ranked:
        c = BY_ID[cid]
        _, why = best_chunk(q, cid)                             # the sentence that matched best
        results.append({**c, "score": score, "why": why})
    return {"query": query, "filters": filters, "results": results}
