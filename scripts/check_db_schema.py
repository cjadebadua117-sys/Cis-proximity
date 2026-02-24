import sqlite3
import sys
path = r'C:\Users\Admin\Desktop\SWRS\db.sqlite3'
con = sqlite3.connect(path)
cur = con.cursor()
try:
    cur.execute("PRAGMA table_info('presence_app_laboratoryhistory')")
    cols = cur.fetchall()
    if not cols:
        print('table_missing_or_empty')
    else:
        for c in cols:
            # PRAGMA returns: cid, name, type, notnull, dflt_value, pk
            print(c)
except Exception as e:
    print('error:', e)
finally:
    con.close()
