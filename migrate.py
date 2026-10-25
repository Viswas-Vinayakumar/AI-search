# migrate.py: copy coaches.json (document style, like Firebase) into the Neon "experts" table
import json
import os

import psycopg
from dotenv import load_dotenv

load_dotenv()                                  # reads .env into environment variables
DB_URL = os.environ["DATABASE_URL_UNPOOLED"]   # direct connection, good for one-off scripts

# 1. EXTRACT: read the JSON documents
with open("data/coaches.json", encoding="utf-8") as f:
    coaches = json.load(f)
print(f"Read {len(coaches)} coaches from JSON")

# 2. TRANSFORM: turn each document into one row, and clean "Online"
rows = []
for c in coaches:
    is_remote = c["city"] == "Online"
    city = None if is_remote else c["city"]
    rows.append((c["id"], c["name"], city, is_remote, c["price"],
                 c["title"], c["title_en"], c["bio"], c["bio_en"]))

# 3. LOAD: insert all rows in one transaction
sql = """
    INSERT INTO experts (id, name, city, is_remote, price_eur,
                         title_de, title_en, bio_de, bio_en)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (id) DO NOTHING
"""
with psycopg.connect(DB_URL) as conn:
    with conn.cursor() as cur:
        cur.executemany(sql, rows)
        cur.execute("SELECT COUNT(*) FROM experts")
        print("Rows in Neon:", cur.fetchone()[0])
# leaving the "with" block saves (commits) everything