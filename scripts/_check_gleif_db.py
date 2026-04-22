"""Quick diagnostic for GLEIF SQLite cache."""
import sqlite3

db = r"C:\Users\ccharm\Desktop\Data\txr_automated_accuracy_testing\gleif\gleif_cache.db"
conn = sqlite3.connect(db)

print("lei_records:", conn.execute("SELECT COUNT(*) FROM lei_records").fetchone()[0])
print("lei_fts:", conn.execute("SELECT COUNT(*) FROM lei_fts").fetchone()[0])

rows_like = conn.execute(
    "SELECT lei, legal_name FROM lei_records WHERE legal_name LIKE ? LIMIT 5",
    ("%AJ Bell%",),
).fetchall()
print("LIKE '%AJ Bell%':", rows_like)

try:
    rows_fts_phrase = conn.execute(
        'SELECT lei, legal_name FROM lei_fts JOIN lei_records r ON lei_fts.rowid = r.rowid'
        ' WHERE lei_fts MATCH ? LIMIT 5',
        ('"AJ Bell"',),
    ).fetchall()
    print("FTS phrase:", rows_fts_phrase)
except Exception as e:
    print("FTS phrase error:", e)

try:
    rows_fts_tokens = conn.execute(
        'SELECT lei, legal_name FROM lei_fts JOIN lei_records r ON lei_fts.rowid = r.rowid'
        ' WHERE lei_fts MATCH ? LIMIT 5',
        ("AJ Bell",),
    ).fetchall()
    print("FTS tokens:", rows_fts_tokens)
except Exception as e:
    print("FTS tokens error:", e)

try:
    rows_fts_prefix = conn.execute(
        'SELECT lei, legal_name FROM lei_fts JOIN lei_records r ON lei_fts.rowid = r.rowid'
        ' WHERE lei_fts MATCH ? LIMIT 5',
        ("AJ*",),
    ).fetchall()
    print("FTS prefix 'AJ*':", rows_fts_prefix)
except Exception as e:
    print("FTS prefix error:", e)

conn.close()
