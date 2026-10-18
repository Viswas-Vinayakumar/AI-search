"""Live demo: type a need in plain German (or English), get matching coaches with a reason.

Run locally:  python app.py
"""
import html

import gradio as gr

from search import METHODS, search

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
    "Gehalt verhandeln",
    "sales training cold calling",
    "Burnout Prävention online",
    "neue Führungskraft: vom Kollegen zum Chef",
]
FILTER_NAMES = {"city": "City", "max_price": "Max. day rate", "format": "Format"}
FORMAT_NAMES = {"online": "online", "onsite": "on site (vor Ort)"}


def render(out):
    f = out["filters"]
    def show(k, v):
        if k == "format":
            return FORMAT_NAMES[v]
        if k == "max_price":
            return f"{v:,} €".replace(",", ".")
        return v
    understood = " · ".join(f"{FILTER_NAMES[k]}: {show(k, v)}" for k, v in f.items()) or "no filters"
    parts = [f"<p style='margin:0 0 12px'><b>Understood</b> — topic: <i>{html.escape(out['query'])}</i> · {html.escape(understood)}</p>"]
    if not out["results"]:
        parts.append("<p>No coach matches these words or filters. Try other words or remove a filter.</p>")
    for i, c in enumerate(out["results"], start=1):
        price = f"{c['price']:,}".replace(",", ".")              # German style: 1.800 €
        parts.append(f"""
<div style="border:1px solid #d0d0d0;border-radius:10px;padding:12px 14px;margin-bottom:10px">
  <div><b>{i}. {html.escape(c['name'])}</b> · {html.escape(c['title'])} · {html.escape(c['city'])} · {price} € per day</div>
  <div style="color:#666;font-size:0.92em">{html.escape(c['title_en'])}</div>
  <div style="margin-top:6px">Why this coach: <q>{html.escape(c['why'])}</q></div>
  <details style="margin-top:6px;font-size:0.92em"><summary>Full profile (DE / EN)</summary>
    <p>{html.escape(c['bio'])}</p><p style="color:#666">{html.escape(c['bio_en'])}</p></details>
</div>""")
    return "".join(parts)


def compare(text):
    rows = ["| Method | #1 | #2 | #3 |", "|---|---|---|---|"]
    for label, key in METHOD_LABELS.items():
        top = search(text, key, top=3)["results"]
        cells = [f"{c['title_en']} ({c['city']})" for c in top] + ["–"] * (3 - len(top))
        rows.append(f"| {label} | " + " | ".join(cells) + " |")
    return "\n".join(rows)


def run(text, method_label):
    text = (text or "").strip()
    if not text:
        return "<p>Type what you are looking for first.</p>", ""
    return render(search(text, METHOD_LABELS[method_label])), compare(text)


with gr.Blocks(title="Coach search prototype") as demo:
    gr.Markdown(
        "# Coach search · prototype\n"
        "Describe what your company needs in plain words, German or English. "
        "The search understands city, budget and format, finds matching coaches by meaning and keywords, "
        "and shows the sentence that made each coach match.\n\n"
        "*All 30 coach profiles are invented for this demo. Built by Viswas Vinayakumar.*"
    )
    with gr.Row():
        query = gr.Textbox(label="Was suchen Sie? (What are you looking for?)", scale=5,
                           placeholder="z. B. Konfliktlösung für unser Vertriebsteam in Hamburg, max. 2.000 €")
        button = gr.Button("Suchen (search)", variant="primary", scale=1)
    method = gr.Radio(list(METHOD_LABELS), value="Hybrid + chunking", label="Search method")
    results = gr.HTML()
    with gr.Accordion("Compare all methods for this query", open=False):
        comparison = gr.Markdown()
    gr.Examples(EXAMPLES, inputs=query, label="Try an example")
    gr.Markdown("How it was measured: [evaluation on a hand-labelled test set](https://github.com/Viswas-Vinayakumar/AI-search)")

    button.click(run, [query, method], [results, comparison])
    query.submit(run, [query, method], [results, comparison])

if __name__ == "__main__":
    demo.launch()
