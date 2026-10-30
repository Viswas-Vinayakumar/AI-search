"""Live demo (Streamlit version): same search as app.py, different page layer.

Run locally:  streamlit run streamlit_app.py
"""
from html import escape

import streamlit as st

from search import search

METHOD_LABELS = {                                           # the first one is the default
    "Hybrid (best in tests)": "hybrid",
    "Semantic": "vector",
    "Keyword (BM25)": "keyword",
    "Hybrid + chunking": "hybrid_chunk",
    "Semantic + chunking": "vector_chunk",
}
EXAMPLES = [
    "Konfliktlösung für unser Vertriebsteam in Hamburg, vor Ort, max. 2.000 €",
    "Mitarbeiter haben Angst vor der neuen Software",
    "Burnout Prävention online",
    "Gehalt verhandeln",
    "sales training cold calling",
    "neue Führungskraft: vom Kollegen zum Chef",
]
FORMAT_NAMES = {"online": "Online", "onsite": "On site"}

CSS = """
<style>
.eyebrow {font-size: .75rem; font-weight: 600; letter-spacing: .12em; text-transform: uppercase;
          color: #2F5BEA; margin-bottom: .25rem;}
.hero {font-size: 2.1rem; font-weight: 700; letter-spacing: -.02em; line-height: 1.15; margin: 0 0 .5rem;}
.sub {color: #5B6372; font-size: 1.02rem; margin-bottom: .25rem;}
.fine {color: #8A91A0; font-size: .82rem; margin-bottom: 1.4rem;}
.chips {margin: .1rem 0 .6rem;}
.chip {display: inline-block; padding: .15rem .65rem; margin: 0 .35rem .35rem 0; border-radius: 999px;
       font-size: .8rem; background: #EEF2FD; color: #2547C0;}
.chip.grey {background: #F1F3F6; color: #4B5263;}
.understood {font-size: .85rem; color: #5B6372; margin: .2rem 0 .8rem;}
.count {font-size: .85rem; color: #8A91A0; margin: .2rem 0 .4rem;}
.card-top {display: flex; justify-content: space-between; align-items: baseline; gap: 1rem;}
.name {font-size: 1.08rem; font-weight: 600;}
.rank {color: #A0A6B2; font-weight: 600; margin-right: .4rem;}
.price {font-weight: 600; white-space: nowrap;}
.price small {font-weight: 400; color: #8A91A0;}
.title {color: #1C2230; margin-top: .1rem;}
.title-en {color: #8A91A0; font-size: .86rem; margin-bottom: .45rem;}
.why {border-left: 3px solid #2F5BEA; background: #F7F9FE; padding: .5rem .8rem; border-radius: 0 8px 8px 0;
      color: #2E3545; font-size: .92rem; margin: .4rem 0 .2rem;}
.why b {color: #2F5BEA; font-weight: 600; font-size: .75rem; letter-spacing: .06em; text-transform: uppercase;
        display: block; margin-bottom: .1rem;}
.foot {color: #8A91A0; font-size: .82rem; text-align: center; margin-top: 2rem;}
.foot a {color: #2F5BEA; text-decoration: none;}
</style>
"""


def euro(n):
    return f"{n:,} €".replace(",", ".")                      # German style: 1.800 €


def chip(text, grey=False):
    return f'<span class="chip{" grey" if grey else ""}">{escape(str(text))}</span>'


@st.cache_resource                                          # load the model and vectors once, not on every click
def warm_up():
    search("Test", "hybrid_chunk")                      # loads the model, profile and chunk vectors
    return True


def use_example():
    if st.session_state.get("example"):
        st.session_state.query = st.session_state.example


def clear_example():
    st.session_state.example = None                         # typing your own text un-highlights the example


st.set_page_config(page_title="Coach search", page_icon="🔎", layout="centered")
st.markdown(CSS, unsafe_allow_html=True)

st.markdown(
    '<div class="eyebrow">AI search prototype</div>'
    '<div class="hero">Find the right coach, in your own words</div>'
    '<div class="sub">Describe what your team needs in German or English. The search reads city, budget '
    'and format, finds coaches by meaning and keywords, and shows why each one fits.</div>'
    '<div class="fine">30 invented coach profiles · built by Viswas Vinayakumar</div>',
    unsafe_allow_html=True,
)

with st.spinner("Loading the language model (first visit only, about 30 seconds)…"):
    warm_up()

if "query" not in st.session_state:
    st.session_state.query = ""

query = st.text_input(
    "What are you looking for?", key="query", label_visibility="collapsed", on_change=clear_example,
    placeholder="e.g. Konfliktlösung für unser Vertriebsteam in Hamburg, max. 2.000 €",
)
st.pills("Try an example", EXAMPLES, key="example", on_change=use_example)

with st.expander("Search method"):
    method_label = st.radio("Search method", list(METHOD_LABELS), label_visibility="collapsed")

if query.strip():
    out = search(query.strip(), METHOD_LABELS[method_label])
    f = out["filters"]

    parts = [chip(f"Topic: {out['query']}")]
    if "city" in f:
        parts.append(chip(f"City: {f['city']}", grey=True))
    if "max_price" in f:
        parts.append(chip(f"Up to {euro(f['max_price'])} / day", grey=True))
    if "format" in f:
        parts.append(chip(FORMAT_NAMES[f["format"]], grey=True))
    st.markdown(f'<div class="understood">Understood</div><div class="chips">{"".join(parts)}</div>',
                unsafe_allow_html=True)

    results = out["results"]
    if not results:
        st.info("No coach matches these words or filters. Try other words or remove a filter.")
    else:
        st.markdown(f'<div class="count">{len(results)} matching coaches</div>', unsafe_allow_html=True)

    for i, c in enumerate(results, start=1):
        place = "Online" if c["city"] == "Online" else f"{c['city']} · on site"
        with st.container(border=True):
            st.markdown(
                f'<div class="card-top"><div class="name"><span class="rank">{i:02d}</span>{escape(c["name"])}</div>'
                f'<div class="price">{euro(c["price"])} <small>/ day</small></div></div>'
                f'<div class="title">{escape(c["title"])}</div>'
                f'<div class="title-en">{escape(c["title_en"])}</div>'
                f'<div class="chips">{chip(place, grey=True)}</div>'
                f'<div class="why"><b>Why this coach</b>“{escape(c["why"])}”</div>',
                unsafe_allow_html=True,
            )
            with st.expander("Full profile (DE / EN)"):
                st.write(c["bio"])
                st.caption(c["bio_en"])

    with st.expander("Compare all methods for this query"):
        rows = []
        for label, key in METHOD_LABELS.items():
            top = search(query.strip(), key, top=3)["results"]
            names = [f"{c['title_en']} ({c['city']})" for c in top] + ["–"] * (3 - len(top))
            rows.append({"Method": label, "#1": names[0], "#2": names[1], "#3": names[2]})
        st.dataframe(rows, hide_index=True)

st.markdown(
    '<div class="foot">How it was measured: '
    '<a href="https://github.com/Viswas-Vinayakumar/AI-search" target="_blank">evaluation on a hand-labelled test set</a>'
    '</div>',
    unsafe_allow_html=True,
)
