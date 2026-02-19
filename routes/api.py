from flask import Blueprint, request, jsonify
import psutil
import platform
import threading
import re
from datetime import datetime
from database import get_connection, update_modo_manual, log_mensaje_sql
from services.meta import enviar_mensaje
from config import USUARIOS_VALIDOS, NUMERO_LLAMADA, SQL_CONN_STR
from functools import wraps

api_bp = Blueprint('api', __name__)

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not (auth.username in USUARIOS_VALIDOS and USUARIOS_VALIDOS[auth.username] == auth.password):
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated

@api_bp.route('/api/heartbeat', methods=['GET'])
def heartbeat():
    cpu_usage = psutil.cpu_percent(interval=None)
    ram = psutil.virtual_memory()
    return jsonify({
        "bot": "MIA WhatsApp Modular",
        "status": "Online" if cpu_usage < 90 else "Warning - High CPU",
        "timestamp": datetime.now().isoformat(),
        "system": {
            "cpu_percent": cpu_usage,
            "ram_percent": ram.percent,
            "os": platform.system(),
            "threads": threading.active_count()
        }
    }), 200

@api_bp.route('/enviar_manual', methods=['POST'])
@requires_auth 
def enviar_manual():
    try:
        d = request.get_json()
        telefono, texto = d['telefono'], d['texto']
        enviar_mensaje(telefono, texto)
        log_mensaje_sql(telefono, "[INTERVENCION_HUMANA]", texto, "MANUAL", 1)
        update_modo_manual(telefono, 1)
        return jsonify({"status": "ok", "modo": "manual"})
    except Exception as e: 
        return jsonify({"error": str(e)}), 500

@api_bp.route('/api/chats')
@requires_auth 
def api_chats():
    try:
        import pyodbc
        with pyodbc.connect(SQL_CONN_STR) as conn:
            cursor = conn.cursor()
            search_term = request.args.get('q', '').strip()
            filtro_extra = ""
            params = []

            if search_term:
                if re.match(r'^\d+$', search_term):
                    filtro_extra = " AND (telefono_conversacion LIKE ? OR telefono LIKE ?) "
                    params.extend([f"%{search_term}%", f"%{search_term}%"])
                else:
                    filtro_extra = " AND (telefono_conversacion IN (SELECT DISTINCT telefono FROM tb_mia_logs_mensajes WHERE mensaje_usuario LIKE ? OR respuesta_bot LIKE ?)) "
                    params.extend([f"%{search_term}%", f"%{search_term}%"])

            query = f"SELECT TOP 100 * FROM dbo.vw_resumen_numeros_mia WHERE 1=1 {filtro_extra} ORDER BY ultima_interaccion DESC"
            cursor.execute(query, params)
            
            columnas = [column[0].lower() for column in cursor.description]
            chats = []
            ahora = datetime.now()
            
            for row in cursor.fetchall():
                r = dict(zip(columnas, row)) 
                tel = r.get('telefono_conversacion') or r.get('telefono', '')
                ultima_fecha = r.get('ultima_interaccion')
                
                fecha_str = ultima_fecha.strftime("%d/%m %H:%M") if ultima_fecha else "Nuevo"
                f_estatus = r.get('fecha_estatus') or r.get('fechaestatus')
                f_estatus_str = f_estatus.strftime("%d/%m") if hasattr(f_estatus, 'strftime') else "-"

                # Calculation for ventana_24h
                ventana_abierta = False
                if ultima_fecha:
                    if (datetime.now() - ultima_fecha).total_seconds() < (24 * 3600):
                        ventana_abierta = True

                chats.append({
                    "telefono": tel,
                    "fecha": fecha_str,
                    "estado": "MANUAL" if r.get('modo_manual') == 1 else r.get('estado_actual', ''),
                    "estatus_ok": str(r.get('estatus_ok', '-')).strip() or '-',
                    "estatus_conversacion": str(r.get('estatus_telefono_conversacion', 'SIN BARRER')).strip() or 'SIN BARRER',
                    "calificado": r.get('lead_calificado', 0),
                    "ventana_24h": ventana_abierta,
                    "comentarios": r.get('comentarios', ''),
                    "info_portabilidad": {
                        "numero_portar": r.get('numero_a_portar', '-'), 
                        "estatus": r.get('estatus', '-'), 
                        "fecha_estatus": f_estatus_str, 
                        "lugar": r.get('lugar', '-')
                    }
                })
            return jsonify(chats)
    except Exception as e: 
        print(f"❌ ERROR API CHATS: {e}")
        return jsonify([])

@api_bp.route('/api/historial/<telefono>')
@requires_auth
def api_historial(telefono):
    try:
        import pyodbc
        with pyodbc.connect(SQL_CONN_STR) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT mensaje_usuario, respuesta_bot, estado_en_ese_momento, fecha_registro FROM tb_mia_logs_mensajes WHERE telefono = ? ORDER BY fecha_registro ASC", (telefono,))
            logs = [{"mensaje_usuario": r[0], "respuesta_bot": r[1], "estado": r[2], "fecha": r[3].strftime("%d/%m %H:%M")} for r in cursor.fetchall()]
            return jsonify(logs)
    except: 
        return jsonify([])

@api_bp.route('/api/reactivar/<telefono>', methods=['POST'])
@requires_auth
def reactivar_bot(telefono):
    update_modo_manual(telefono, 0)
    return jsonify({"status": "ok"})

@api_bp.route('/api/guardar_comentario', methods=['POST'])
@requires_auth
def guardar_comentario():
    try:
        d = request.get_json()
        telefono, comentario = d.get('telefono'), d.get('comentario')
        import pyodbc
        with pyodbc.connect(SQL_CONN_STR) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE tb_mia_flujo_ventas SET comentarios = ? WHERE telefono = ?", (comentario, telefono))
            conn.commit()
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
