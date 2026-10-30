# embed.py: give every expert WITHOUT a vector one (new or edited profiles)
import os
import psycopg
from dotenv import load_dotenv

load_dotenv()
DB_URL = os.environ["DATABASE_URL_UNPOOLED"]
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def to_pgvector(vec):
    return "[" + ",".join(str(float(x)) for x in vec) + "]"


with psycopg.connect(DB_URL) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT id, title_de, bio_de FROM experts WHERE embedding IS NULL ORDER BY id")
        rows = cur.fetchall()

        if rows:
            from sentence_transformers import SentenceTransformer   # load the model only if needed
            model = SentenceTransformer(MODEL_NAME)
            texts = [f"{title}. {bio}" for _, title, bio in rows]   # same recipe as the prototype
            vectors = model.encode(texts, normalize_embeddings=True)
            for (expert_id, _, _), vec in zip(rows, vectors):
                cur.execute("UPDATE experts SET embedding = %s::vector WHERE id = %s",
                            (to_pgvector(vec), expert_id))

        print("Embedded now:", len(rows))
        cur.execute("SELECT COUNT(*) FROM experts WHERE embedding IS NOT NULL")
        print("Experts with embeddings:", cur.fetchone()[0])