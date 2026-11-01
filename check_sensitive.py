import sqlite3
conn = sqlite3.connect('/app/data/smarthome.db')
c = conn.cursor()

# Check users table
c.execute('SELECT email, password_hash, display_name FROM users')
rows = c.fetchall()
print("=== USERS ===")
for r in rows:
    email = r[0]
    pwd_hash = r[1]
    name = r[2]
    print(f"  {email} | hash: {pwd_hash[:20]}... | name: {name}")

# Check collector_devices
c.execute('SELECT id, name, token_hash, token_hint FROM collector_devices')
rows = c.fetchall()
print("\n=== COLLECTOR DEVICES ===")
for r in rows:
    print(f"  id={r[0]} name={r[1]} token_hash={r[2][:20]}... hint={r[3]}")

# Check home_shares
c.execute('SELECT code, home_id, created_by, expires_at FROM home_shares')
rows = c.fetchall()
print("\n=== HOME SHARES ===")
for r in rows:
    print(f"  code={r[0]} home={r[1]} by={r[2]} expires={r[3]}")

# Check alerts
c.execute('SELECT count(*) FROM alerts')
count = c.fetchone()[0]
print(f"\n=== ALERTS COUNT: {count} ===")