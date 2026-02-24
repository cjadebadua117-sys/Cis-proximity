import sqlite3
path = r'C:\Users\Admin\Desktop\SWRS\db.sqlite3'
con = sqlite3.connect(path)
cur = con.cursor()
cur.execute("SELECT app, name FROM django_migrations WHERE app='presence_app'")
rows = cur.fetchall()
print(rows)
con.close()