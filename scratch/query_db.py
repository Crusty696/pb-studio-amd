import sqlite3

db_path = r"C:\Users\david\Documents\PBStudio\Klangkraft_E2E_1780357792\state.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Tabellennamen auslesen
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [t[0] for t in cursor.fetchall()]
print("Tabellen in DB:", tables)

# Zeilen in allen Tabellen zählen
for table in tables:
    try:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"  {table}: {count} Zeilen")
    except Exception as e:
        print(f"  Error reading {table}: {e}")

conn.close()
