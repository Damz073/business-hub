from app.database import conectar

TELEFONE = "557398134641"  # <<< troque se quiser outro número

conn = conectar()
cur = conn.cursor()

print(f"Limpando dados do telefone: {TELEFONE}")

# 🧠 Sessões de chat
try:
    cur.execute("DELETE FROM chat_sessions WHERE phone = ?", (TELEFONE,))
    print("✔ chat_sessions limpo")
except Exception as e:
    print("⚠ chat_sessions:", e)

# 💬 Mensagens
try:
    cur.execute("DELETE FROM chat_messages WHERE phone = ?", (TELEFONE,))
    print("✔ chat_messages limpo")
except Exception as e:
    print("⚠ chat_messages:", e)

# 🧾 Cotações / pedidos de reserva
try:
    cur.execute("DELETE FROM reservation_requests WHERE customer_phone = ?", (TELEFONE,))
    print("✔ reservation_requests limpo")
except Exception as e:
    print("⚠ reservation_requests:", e)

# 🏨 Reservas criadas
try:
    cur.execute("DELETE FROM reservations WHERE customer_phone = ?", (TELEFONE,))
    print("✔ reservations limpo")
except Exception as e:
    print("⚠ reservations:", e)

conn.commit()
conn.close()

print("✅ Reset finalizado")