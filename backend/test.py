import sqlite3

DB_PATH = "worldcup_stats.db"  # change if needed

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Get all tables
tables = cur.execute("""
SELECT name
FROM sqlite_master
WHERE type='table'
AND name NOT LIKE 'sqlite_%'
ORDER BY name;
""").fetchall()

for table in tables:
    table_name = table["name"]

    print("=" * 80)
    print(f"TABLE: {table_name}")
    print("=" * 80)

    # CREATE TABLE statement
    create_sql = cur.execute("""
        SELECT sql
        FROM sqlite_master
        WHERE type='table' AND name=?
    """, (table_name,)).fetchone()

    print("\nCREATE STATEMENT:")
    print(create_sql["sql"])

    # Columns
    print("\nCOLUMNS:")
    cols = cur.execute(f"PRAGMA table_info('{table_name}')").fetchall()

    for c in cols:
        print(
            f"  {c['name']:<25}"
            f"type={c['type']:<15}"
            f"not_null={c['notnull']} "
            f"pk={c['pk']} "
            f"default={c['dflt_value']}"
        )

    # Foreign Keys
    fks = cur.execute(f"PRAGMA foreign_key_list('{table_name}')").fetchall()
    if fks:
        print("\nFOREIGN KEYS:")
        for fk in fks:
            print(
                f"  {fk['from']} -> "
                f"{fk['table']}.{fk['to']} "
                f"(on_update={fk['on_update']}, on_delete={fk['on_delete']})"
            )

    # Indexes
    indexes = cur.execute(f"PRAGMA index_list('{table_name}')").fetchall()
    if indexes:
        print("\nINDEXES:")
        for idx in indexes:
            print(f"  {idx['name']} (unique={idx['unique']})")

            idx_cols = cur.execute(
                f"PRAGMA index_info('{idx['name']}')"
            ).fetchall()

            print("    Columns:", ", ".join(col["name"] for col in idx_cols))

    print("\n")

conn.close()