"""Live demo (Streamlit version): same search as app.py, different page layer.

Run locally:  streamlit run streamlit_app.py
"""
import streamlit as st

from search import search

METHOD_LABELS = {
    "Hybrid + chunking": "hybrid_chunk",
    "Hybrid": "hybrid",
    "Semantic + chunking": "vector_chunk",
    "Semantic": "vector",
    "Keyword (BM25)": "keyword",
}
EXAMPLES = [
    "Konfliktlösung für unser Vertriebsteam in Hamburg, vor Ort, max. 2.000 €",
    "Mitarbeiter haben Angst vor der neuen Software",
    "Burnout Prävention online",
    "Gehalt verhandeln",
    "sales training cold calling",
    "neue Führungskraft: vom Kollegen zum Chef",
]
FILTER_NAMES = {"city": "City", "max_price": "Max. day rate", "format": "Format"}
FORMAT_NAMES = {"online": "online", "onsite": "on site (vor Ort)"}


def euro(n):
    return f"{n:,} €".replace(",", ".")                      # German style: 1.800 €


@st.cache_resource                                          # load the model and vectors once, not on every click
def warm_up():
    search("Test", "hybrid_chunk")
    return True


st.set_page_config(page_title="Coach search prototype", page_icon="🔎")
st.title("Coach search · prototype")
st.write(
    "Describe what your company needs in plain words, German or English. "
    "The search understands city, budget and format, finds matching coaches by meaning and keywords, "
    "and shows the sentence that made each coach match."
)
st.caption("All 30 coach profiles are invented for this demo. Built by Viswas Vinayakumar.")

with st.spinner("Loading the language model (first visit only, about 30 seconds)…"):
    warm_up()

if "query" not in st.session_state:
    st.session_state.query = ""

st.write("**Try an example:**")
cols = st.columns(3)
for i, ex in enumerate(EXAMPLES):
    if cols[i % 3].button(ex, key=f"ex{i}", use_container_width=True):
        st.session_state.query = ex

query = st.text_input("Was suchen Sie? (What are you looking for?)", key="query",
                      placeholder="z. B. Konfliktlösung für unser Vertriebsteam in Hamburg, max. 2.000 €")
method_label = st.radio("Search method", list(METHOD_LABELS), horizontal=True)

if query.strip():
    out = search(query.strip(), METHOD_LABELS[method_label])
    f = out["filters"]
    shown = []
    for k, v in f.items():
        shown.append(f"{FILTER_NAMES[k]}: {FORMAT_NAMES[v] if k == 'format' else euro(v) if k == 'max_price' else v}")
    st.markdown(f"**Understood** — topic: *{out['query']}* · " + (" · ".join(shown) or "no filters"))

    if not out["results"]:
        st.info("No coach matches these words or filters. Try other words or remove a filter.")
    for i, c in enumerate(out["results"], start=1):
        with st.container(border=True):
            st.markdown(f"**{i}. {c['name']}** · {c['title']} · {c['city']} · {euro(c['price'])} per day")
            st.caption(c["title_en"])
            st.markdown(f"Why this coach: “{c['why']}”")
            with st.expander("Full profile (DE / EN)"):
                st.write(c["bio"])
                st.caption(c["bio_en"])

    with st.expander("Compare all methods for this query"):
        rows = []
        for label, key in METHOD_LABELS.items():
            top = search(query.strip(), key, top=3)["results"]
            names = [f"{c['title_en']} ({c['city']})" for c in top] + ["–"] * (3 - len(top))
            rows.append({"Method": label, "#1": names[0], "#2": names[1], "#3": names[2]})
        st.table(rows)

st.markdown("---")
st.markdown("How it was measured: [evaluation on a hand-labelled test set](https://github.com/Viswas-Vinayakumar/AI-search)")
