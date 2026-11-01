import sqlite3
conn = sqlite3.connect('/app/data/smarthome.db')
c = conn.cursor()
tables = ['wifi_scans','collection_sessions','predictions','alerts','sensor_samples']
for t in tables:
    c.execute(f'SELECT count(*) FROM {t}')
    print(f'{t}: {c.fetchone()[0]}')