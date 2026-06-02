import sqlite3

from db import DB_PATH


conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute("""
INSERT INTO matches (
    id,
    home_team,
    away_team,
    start_time,
    status,
    processed
)
VALUES (
    1,
    'Brazil',
    'Argentina',
    '2026-06-01T18:00:00Z',
    'scheduled',
    0
)
ON CONFLICT(id) DO UPDATE SET
    home_team = excluded.home_team,
    away_team = excluded.away_team,
    start_time = excluded.start_time,
    status = excluded.status,
    processed = excluded.processed
""")

conn.commit()
print(f"Match added to {DB_PATH}")
conn.close()
