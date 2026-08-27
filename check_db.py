import sqlite3

conn = sqlite3.connect('db.sqlite3')
cursor = conn.cursor()

# List all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = cursor.fetchall()
print("=== TABLES ===")
for t in tables:
    print(t[0])

# Count rows in each table
print("\n=== ROW COUNTS ===")
for t in tables:
    name = t[0]
    if name.startswith('sqlite_'):
        continue
    try:
        cursor.execute(f'SELECT COUNT(*) FROM "{name}"')
        count = cursor.fetchone()[0]
        print(f"{name}: {count}")
    except:
        print(f"{name}: error")

# Show schema of key tables
for tbl in ['effiadmi_producto', 'effiadmi_product', 'effiadmi_inventario', 'effiadmi_inventory', 'effiadmi_movimientos', 'effiadmi_inventorylog', 'effiadmi_branch']:
    try:
        cursor.execute(f'PRAGMA table_info("{tbl}")')
        cols = cursor.fetchall()
        if cols:
            print(f"\n=== {tbl} columns ===")
            for c in cols:
                print(f"  {c[1]} ({c[2]})")
    except:
        pass

conn.close()
