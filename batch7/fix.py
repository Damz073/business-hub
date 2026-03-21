from app.database import conectar

conn = conectar()
cur = conn.cursor()

cur.execute("UPDATE businesses SET business_type='hospitality'")

conn.commit()
conn.close()

print("ok")