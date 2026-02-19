import pyodbc
import json
import re
from datetime import datetime, timedelta
from config import SQL_CONN_STR, DIAS_REINICIO, HISTORY_LIMIT

def get_connection():
    return pyodbc.connect(SQL_CONN_STR)

def insertar_referido(telefono, tipo_insercion="Portar"):
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT count(*) FROM prepago..Referidos WHERE numero = ? AND CAST(fechainserto AS DATE) = CAST(GETDATE() AS DATE) AND empleado = 'Mia'", (telefono,))
            if cursor.fetchone()[0] == 0:
                query = "INSERT INTO prepago..Referidos (numero, fechainserto, lugar, empleado) VALUES (?, GETDATE(), 'ValidadorPagina', 'Mia')"
                cursor.execute(query, (telefono,))
                conn.commit()
                print(f"[{telefono}] ✅ [SQL INSERT] ¡Guardado exitosamente! (Origen: {tipo_insercion})")
            else:
                print(f"[{telefono}] ⚠️ [SQL] El número ya estaba registrado hoy (Anti-Duplicado).")
    except Exception as e: 
        print(f"[{telefono}] ❌ [SQL ERROR] Referidos: {e}")

def get_sesion_sql(telefono):
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT estado_actual, datos_contexto, lead_calificado, modo_manual, ultima_interaccion, numero_a_portar FROM tb_mia_flujo_ventas WITH (NOLOCK) WHERE telefono = ?"
            cursor.execute(query, (telefono,))
            row = cursor.fetchone()
            if row:
                estado, fecha, num_guardado = row[0], row[4], row[5]
                if fecha and (datetime.now() - fecha) > timedelta(days=DIAS_REINICIO):
                    return {"state": "NUEVO", "data": {}, "calificado": 0, "manual": 0, "num_portar": None}
                return {"state": estado, "data": json.loads(row[1]), "calificado": row[2], "manual": row[3], "num_portar": num_guardado}
            return {"state": "NUEVO", "data": {}, "calificado": 0, "manual": 0, "num_portar": None}
    except: 
        return {"state": "NUEVO", "data": {}, "calificado": 0, "manual": 0, "num_portar": None}

def update_sesion_sql(telefono, estado, data, calificado=0, campana=None, num_portar=None, agenda=None):
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            json_str = json.dumps(data)
            cursor.execute("SELECT count(*) FROM tb_mia_flujo_ventas WITH (NOLOCK) WHERE telefono = ?", (telefono,))
            if cursor.fetchone()[0] > 0:
                query = "UPDATE tb_mia_flujo_ventas SET estado_actual=?, datos_contexto=?, lead_calificado=?, ultima_interaccion=GETDATE(), es_activo=1"
                params = [estado, json_str, calificado]
                if num_portar: 
                    query += ", numero_a_portar=?"
                    params.append(num_portar)
                if agenda: 
                    query += ", horario_agenda=?"
                    params.append(agenda)
                query += " WHERE telefono=?"
                params.append(telefono)
            else:
                query = "INSERT INTO tb_mia_flujo_ventas (telefono, estado_actual, datos_contexto, lead_calificado, origen_campana, es_activo, ultima_interaccion, modo_manual, numero_a_portar, horario_agenda) VALUES (?, ?, ?, ?, ?, 1, GETDATE(), 0, ?, ?)"
                params = [telefono, estado, json_str, calificado, campana or "organico", num_portar, agenda]
            cursor.execute(query, params)
            conn.commit()
    except Exception as e: 
        print(f"❌ [SQL UPDATE ERROR] {e}")

def log_mensaje_sql(tel, msg, resp, est, calif):
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO tb_mia_logs_mensajes (telefono, mensaje_usuario, respuesta_bot, estado_en_ese_momento, fecha_registro, lead_calificado_al_momento) VALUES (?, ?, ?, ?, GETDATE(), ?)", (tel, msg, resp, est, calif))
            conn.commit()
    except: 
        pass

def get_historial_chat(telefono):
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT TOP {HISTORY_LIMIT} mensaje_usuario, respuesta_bot FROM tb_mia_logs_mensajes WITH (NOLOCK) WHERE telefono = ? ORDER BY id_log DESC", (telefono,))
            rows = cursor.fetchall()
            historial = ""
            for row in reversed(rows): 
                historial += f"Cliente: {row[0]}\nMia: {row[1]}\n"
            return historial
    except: 
        return ""

def update_modo_manual(telefono, modo_manual=1):
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE tb_mia_flujo_ventas SET modo_manual = ?, ultima_interaccion = GETDATE() WHERE telefono = ?", (modo_manual, telefono))
            conn.commit()
    except Exception as e:
        print(f"❌ [SQL MANUAL ERROR] {e}")
