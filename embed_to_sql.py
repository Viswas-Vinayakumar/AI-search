# embed_to_sql.py: Plan B when your network blocks Postgres (port 5432).
# Computes the vectors on your Mac (no database needed) and writes them into
# embeddings.sql. Then paste that file into the Neon SQL Editor and click Run.
import json

from sentence_transformers import SentenceTransformer

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

with open("data/coaches.json", encoding="utf-8") as f:
    coaches = json.load(f)
print(f"Read {len(coaches)} coaches")

model = SentenceTransformer(MODEL_NAME)
print("Model loaded")

texts = [f"{c['title']}. {c['bio']}" for c in coaches]      # same recipe as the prototype and embed.py
vectors = model.encode(texts, normalize_embeddings=True)
print("Vectors ready")

with open("embeddings.sql", "w", encoding="utf-8") as out:
    for c, vec in zip(coaches, vectors):
        vec_text = "[" + ",".join(f"{float(x):.6f}" for x in vec) + "]"
        out.write(f"UPDATE experts SET embedding = '{vec_text}'::vector WHERE id = '{c['id']}';\n")
    out.write("SELECT COUNT(*) AS experts_with_embeddings FROM experts WHERE embedding IS NOT NULL;\n")

print("Done: open embeddings.sql, copy everything, paste into the Neon SQL Editor, click Run")
