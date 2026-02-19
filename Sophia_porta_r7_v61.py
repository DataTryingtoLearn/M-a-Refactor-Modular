
import socket
import psutil
import platform
import os
import json
import requests
import pyodbc
import logging
import re
import time 
import threading 
import random 
import pytz 
import sys 
from datetime import timedelta, datetime
from functools import wraps 
from flask import Flask, request, jsonify, render_template, Response 
from dotenv import load_dotenv

# 🔥 USAMOS LA LIBRERÍA INSTALADA
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

# ==========================================
# 1. CONFIGURACIÓN Y LOGGING DUAL
# ==========================================
load_dotenv()
app = Flask(__name__)

NUMERO_LLAMADA = os.getenv("NUMERO_LLAMADA", "2292349024")

# --- CLASE PARA DUPLICAR LA SALIDA (Consola -> Archivo) ---
class DualLogger:
    def __init__(self, filename):
        self.terminal = sys.stdout
        self.filename = filename
        self.current_date = datetime.now().strftime("%Y-%m-%d")
        self._lock = threading.Lock()

        self.current_filename = self._get_filename_for_date(self.current_date)
        self.log_file = open(self.current_filename, "a", encoding="utf-8")

    def _get_filename_for_date(self, date_str):
        if re.search(r"\d{4}-\d{2}-\d{2}", self.filename):
            return re.sub(r"\d{4}-\d{2}-\d{2}", date_str, self.filename)
        return self.filename

    def _rotate_if_needed(self):
        hoy = datetime.now().strftime("%Y-%m-%d")
        if hoy != self.current_date:
            self.current_date = hoy
            nuevo = self._get_filename_for_date(hoy)
            if nuevo != self.current_filename:
                try:
                    self.log_file.close()
                except:
                    pass
                self.current_filename = nuevo
                self.log_file = open(self.current_filename, "a", encoding="utf-8")

    def write(self, message):
        with self._lock:
            self._rotate_if_needed()
            self.terminal.write(message) 
            self.log_file.write(message) 
            self.log_file.flush()        

    def flush(self):
        with self._lock:
            self.terminal.flush()
            self.log_file.flush()

# Configuración del nombre del archivo
fecha_hoy = datetime.now().strftime("%Y-%m-%d")
nombre_log = os.path.join(r"D:\Proyectos\Logs", f"mia_log_{fecha_hoy}.log")
os.makedirs(r"D:\Proyectos\Logs", exist_ok=True)

sys.stdout = DualLogger(nombre_log)
sys.stderr = DualLogger(nombre_log)

print(f"📝 [SISTEMA] Iniciando MIA V62 (Anti-Lag, IP Local y Rastreo Temprano)...")

# --- FUNCIÓN DE LECTURA ROBUSTA ---
def leer_txt(nombre_archivo): 
    try: 
        if not nombre_archivo: return ""
        carpeta_base = r"D:\Documentos_Mia" 
        ruta_completa = os.path.join(carpeta_base, nombre_archivo)
        with open(ruta_completa, 'r', encoding='utf-8') as archivo: 
            return archivo.read()
    except Exception as e: 
        print(f"⚠️ [FILE ERROR] No se pudo leer {nombre_archivo}: {e}")
        return "" 

# Carga de Contexto
PROMO_TXT = leer_txt("Promociones.txt")
FAQ_TEXTO = leer_txt("Faq_Prepago_R7.txt")
KB_TEXTO = leer_txt("Bd_Conocimientos_Prepago_R7.txt") 

if not PROMO_TXT or len(PROMO_TXT) < 10:
    PROMO_TXT = """
    👉 $50 x 25 días: 2.5GB de internet
    👉 $100 x 30 días: 5.5GB de internet
    🎁 Redes Sociales ILIMITADAS + Prime Video Básico.
    """

PROMO_SHORT = "✨ ¡Cámbiate a Telcel! Obtén 5.5GB, Redes Sociales Ilimitadas 🎁 y Prime Video 📺 recargando solo $100. Chip y trámite GRATIS."
AVISO_TXT_CORTO = "Consulta nuestro aviso de privacidad en: https://www.telcel.com/aviso-de-privacidad"

# --- IA CONFIG ---
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
safety_settings = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE, 
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE, 
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE, 
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE
}
model = genai.GenerativeModel("gemini-2.5-flash", generation_config={"temperature": 0.3}, safety_settings=safety_settings)

# Credenciales Meta
TOKEN_META = os.getenv("FACEBOOK_ACCESS_TOKEN") 
PHONE_ID = os.getenv("FACEBOOK_PHONE_NUMBER_ID") 
VERIFY_TOKEN = os.getenv("FACEBOOK_VERIFY_TOKEN", "HOLA_MIA")

# Configuración Negocio
DIAS_REINICIO = float(os.getenv("DIAS_REINICIO", 1.0))
HISTORY_LIMIT = int(os.getenv("HISTORY_LIMIT", 5))
RANGOS_LISTA = [x.strip() for x in os.getenv("RANGOS_AGENDA", "09-11 AM,11-01 PM,04-06 PM,Despues 06 PM").split(',')]

message_buffers = {} 
active_timers = {}   
SQL_CONN_STR = (f"DRIVER={{{os.getenv('SQL_DRIVER', 'ODBC Driver 17 for SQL Server')}}};SERVER={os.getenv('SQL_SERVER')};DATABASE={os.getenv('SQL_DATABASE')};UID={os.getenv('SQL_USERNAME')};PWD={os.getenv('SQL_PASSWORD')}")

# ==========================================
# 🔐 SEGURIDAD: MULTI-USUARIO 
# ==========================================
USUARIOS_VALIDOS = {
    "E029973": "E029973JO", 
    "E019588": "E019588CS",
    "E029863": "E029863MM",
    "E015379": "E015379CG",
    "E041364": "E041364IG"
}

def check_auth(username, password):
    return username in USUARIOS_VALIDOS and USUARIOS_VALIDOS[username] == password

def authenticate():
    return Response(
        '⚠️ Acceso denegado. Credenciales incorrectas.\n', 401,
        {'WWW-Authenticate': 'Basic realm="MIA Dashboard Login"'})

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

# ==========================================
# 2. BASE DE DATOS
# ==========================================
def insertar_referido(telefono, tipo_insercion="Portar"):
    try:
        conn = pyodbc.connect(SQL_CONN_STR)
        cursor = conn.cursor()
        # Verifica si ese número exacto ya se insertó HOY
        cursor.execute("SELECT count(*) FROM prepago..Referidos WHERE numero = ? AND CAST(fechainserto AS DATE) = CAST(GETDATE() AS DATE) AND empleado = 'Mia'", (telefono,))
        if cursor.fetchone()[0] == 0:
            query = "INSERT INTO prepago..Referidos (numero, fechainserto, lugar, empleado) VALUES (?, GETDATE(), 'ValidadorPagina', 'Mia')"
            cursor.execute(query, (telefono,))
            conn.commit()
            print(f"[{telefono}] ✅ [SQL INSERT] ¡Guardado exitosamente! (Origen: {tipo_insercion})")
        else:
            print(f"[{telefono}] ⚠️ [SQL] El número ya estaba registrado hoy (Anti-Duplicado).")
        conn.close()
    except Exception as e: 
        print(f"[{telefono}] ❌ [SQL ERROR] Referidos: {e}")

def get_sesion_sql(telefono):
    try:
        conn = pyodbc.connect(SQL_CONN_STR)
        cursor = conn.cursor()
        query = "SELECT estado_actual, datos_contexto, lead_calificado, modo_manual, ultima_interaccion, numero_a_portar FROM tb_mia_flujo_ventas WITH (NOLOCK) WHERE telefono = ?"
        cursor.execute(query, (telefono,))
        row = cursor.fetchone()
        conn.close()
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
        conn = pyodbc.connect(SQL_CONN_STR)
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
        conn.close()
    except Exception as e: 
        print(f"❌ [SQL UPDATE ERROR] {e}")

def log_mensaje_sql(tel, msg, resp, est, calif):
    try:
        conn = pyodbc.connect(SQL_CONN_STR)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO tb_mia_logs_mensajes (telefono, mensaje_usuario, respuesta_bot, estado_en_ese_momento, fecha_registro, lead_calificado_al_momento) VALUES (?, ?, ?, ?, GETDATE(), ?)", (tel, msg, resp, est, calif))
        conn.commit()
        conn.close()
    except: 
        pass

def get_historial_chat(telefono):
    try:
        conn = pyodbc.connect(SQL_CONN_STR)
        cursor = conn.cursor()
        cursor.execute(f"SELECT TOP {HISTORY_LIMIT} mensaje_usuario, respuesta_bot FROM tb_mia_logs_mensajes WITH (NOLOCK) WHERE telefono = ? ORDER BY id_log DESC", (telefono,))
        rows = cursor.fetchall()
        conn.close()
        historial = ""
        for row in reversed(rows): 
            historial += f"Cliente: {row[0]}\nMia: {row[1]}\n"
        return historial
    except: 
        return ""

def enviar_mensaje(telefono, texto):
    url = f"https://graph.facebook.com/v19.0/{PHONE_ID}/messages"
    headers = {"Authorization": f"Bearer {TOKEN_META}", "Content-Type": "application/json"}
    data = {"messaging_product": "whatsapp", "to": telefono, "type": "text", "text": {"body": texto}}
    try:
        response = requests.post(url, headers=headers, json=data, timeout=5)
        if response.status_code == 200:
            print(f"✅ [META SEND OK] Mensaje enviado a {telefono}")
        else:
            print(f"🛑 [META SEND ERROR] {response.text}")
    except Exception as e: 
        print(f"❌ Error Conexión Meta: {e}")

def enviar_lista_horarios(telefono, texto_header):
    url = f"https://graph.facebook.com/v19.0/{PHONE_ID}/messages"
    headers = {"Authorization": f"Bearer {TOKEN_META}", "Content-Type": "application/json"}
    rows = [{"id": f"rango_{i}", "title": r[:24]} for i, r in enumerate(RANGOS_LISTA)]
    data = {
        "messaging_product": "whatsapp", 
        "to": telefono, 
        "type": "interactive", 
        "interactive": {
            "type": "list", 
            "header": {"type": "text", "text": "Agenda tu Llamada"}, 
            "body": {"text": texto_header}, 
            "footer": {"text": "Opciones disponibles 👇"}, 
            "action": {
                "button": "Ver Horarios", 
                "sections": [{"title": "Selecciona uno", "rows": rows}]
            }
        }
    }
    try:
        requests.post(url, headers=headers, json=data, timeout=5)
    except Exception as e:
        print(f"❌ Error enviando horarios a Meta: {e}")

# ==========================================
# 🔥 HILO SEGUIMIENTO V67 (DISCRIMINACIÓN INTELIGENTE)
# ==========================================
def hilo_seguimiento():
    print("🕵️‍♂️ [SEGUIMIENTO V67] Iniciado. Modo: Respeto Ventana 24h y Filtros R7.")
    
    # --- DICCIONARIO DE MENSAJES SEGÚN ESTATUS ---
    # Mensajes para Candidatos (No Telcel y en Región)
    MSGS_CANDIDATO = [
        "👀 ¡Hola! Noté que no terminamos tu registro. ¿Todo bien? Recuerda que tienes 5.5GB + Redes esperando 🎁.",
        "👋 ¿Sigues ahí? Solo te recuerdo que el trámite es 100% GRATIS y rápido. ¿Te ayudo a terminar? 👇",
        "⚠️ Último aviso: Tu promoción de 5.5GB está por expirar. ¿Quieres aprovecharla antes de que se vaya? 🚀",
        "💌 ¡Por el mes del amor y la amistad! 💘 No olvides que podrías llevarte tu primera recarga GRATIS. Déjame tu número a 10 dígitos para validarlo 😁👇"
    ]

    # Mensajes para Ya Telcel (Buscamos Referidos)
    MSGS_TELCEL = [
        "💙 ¡Hola! Vi que tu línea ya es Telcel. ¡Qué bueno que eres parte de la familia! Esta promo es para líneas nuevas, ¿conoces a alguien (amigo o familiar) que use AT&T o Movistar o alguna otra!? Pásame su número y les regalamos el beneficio a ellos 🎁✨",
        "👋 ¡No te quedes sin tu recarga gratis!! Aunque tú seas Telcel, puedes dárselo a alguien más. ¿Me pasas el número de un familiar para activarle los 5.5GB? 👇"
    ]

    # Mensajes para Fuera de Región (Solo R7)
    MSGS_REGION = [
        "📍 ¡Hola! Noté que tu zona está fuera de nuestra cobertura  (Puebla, Veracruz, Oaxaca, Guerrero, Tlaxcala). El regalo de San Valentín solo aplica para estos estados. ¿Tienes algún familiar viviendo en estos lugares para pasarle el beneficio? 🎁",
        "⚠️ Solo recordándote que tu recarga gratis y regalo de 5.5GB es exclusiva para los estados que te mencionaba. Si tienes un número de esa zona, pásamelo para validarlo de una vez. 👇"
    ]

    zona_mexico = pytz.timezone('America/Mexico_City')

    while True:
        try:
            ahora_mexico = datetime.now(zona_mexico)
            
            # Solo operamos de 9 AM a 9 PM hora México
            if 8 <= ahora_mexico.hour < 22:
                conn = pyodbc.connect(SQL_CONN_STR)
                cursor = conn.cursor()
                
                # 🔥 QUERY MAESTRA: Basada en fecha_ultimo_mensaje y estatus de la vista
                # Filtramos < 23 para tener un margen de seguridad con la ventana de Meta
                query = """
                SELECT 
                    telefono_conversacion, 
                    ISNULL(intentos_seguimiento, 0), 
                    estatus_telefono_conversacion
                FROM dbo.vw_resumen_numeros_mia WITH (NOLOCK)
                WHERE numero_a_portar IS NULL 
                AND estado_actual NOT IN ('FIN', 'MANUAL')
                AND DATEDIFF(minute, ultima_interaccion, GETDATE()) > 60 
                AND fecha_ultimo_mensaje IS NOT NULL
                AND DATEDIFF(hour, fecha_ultimo_mensaje, GETDATE()) < 23
                """
                cursor.execute(query)
                rows = cursor.fetchall()
                conn.close() 

                if rows:
                    print(f"🕵️‍♂️ [SEGUIMIENTO] Procesando {len(rows)} leads dentro de ventana...")

                for r in rows:
                    tel = r[0]
                    intentos = int(r[1])
                    status_chat = str(r[2]).upper()
                    
                    # --- DETERMINAR MENSAJE Y LÍMITE ---
                    lista_actual = MSGS_CANDIDATO
                    max_intentos_permitidos = 4

                    if status_chat == 'YA ES TELCEL':
                        lista_actual = MSGS_TELCEL
                        max_intentos_permitidos = 2 # Solo 2 toques para referidos
                    elif status_chat == 'FUERAREGION':
                        lista_actual = MSGS_REGION
                        max_intentos_permitidos = 2 # Solo 2 toques para fuera de zona
                    
                    # Si ya cumplió sus intentos, lo saltamos
                    if intentos >= max_intentos_permitidos:
                        continue

                    # Pausa humana aleatoria entre envíos
                    time.sleep(random.uniform(60, 90))

                    try:
                        # Doble validación: Que no haya escrito mientras dormíamos
                        conn_check = pyodbc.connect(SQL_CONN_STR)
                        cursor_check = conn_check.cursor()
                        cursor_check.execute("SELECT count(*) FROM tb_mia_flujo_ventas WHERE telefono = ? AND DATEDIFF(minute, ultima_interaccion, GETDATE()) < 5", (tel,))
                        if cursor_check.fetchone()[0] > 0:
                            conn_check.close()
                            continue 
                        
                        texto_enviar = lista_actual[intentos]
                        print(f"🚀 [ENVIANDO] A {tel} | Estatus: {status_chat} | Intento: {intentos + 1}")
                        
                        enviar_mensaje(tel, texto_enviar)
                        
                        # Actualización de intentos y tiempo
                        cursor_check.execute("""
                            UPDATE tb_mia_flujo_ventas 
                            SET intentos_seguimiento = ?, ultima_interaccion = GETDATE(), estado_actual = 'SEGUIMIENTO' 
                            WHERE telefono = ?
                        """, (intentos + 1, tel))
                        conn_check.commit()
                        conn_check.close()
                        
                        log_mensaje_sql(tel, "[AUTO_SEGUIMIENTO]", texto_enviar, "SEGUIMIENTO", 0)

                    except Exception as e_inner:
                        print(f"❌ Error envío individual {tel}: {e_inner}")

            # Espera 15 minutos para el siguiente barrido
            time.sleep(900) 

        except Exception as e:
            print(f"❌ [ERROR CRÍTICO SEGUIMIENTO]: {e}")
            time.sleep(600) 

# ==========================================
# 4. LÓGICA DE NEGOCIO (V62 - BLINDAJE 100%)
# ==========================================
def ejecutar_logica_batch(telefono, lista_mensajes, nombre, campana_detectada):
    try:
        texto_unificado = " ".join(lista_mensajes)
        prefix = f"[{telefono}]"
        print(f"\n🚀 {prefix} [BATCH] {nombre} dice: {texto_unificado}")
        print(f"🎯 [MARKETING INFO] Fuente detectada: {campana_detectada}")
        
        if telefono in message_buffers: del message_buffers[telefono]
        if telefono in active_timers: del active_timers[telefono]

        sesion = get_sesion_sql(telefono)
        estado, data, calificado = sesion["state"], sesion["data"], sesion["calificado"]
        num_portar_sql = sesion["num_portar"] 
        
        # 🛡️ ESCENARIO 1: MODO MANUAL
        if sesion["manual"] == 1: 
            print(f"⛔ {prefix} [MANUAL ACTIVADO] El humano tiene el control.")
            log_mensaje_sql(telefono, texto_unificado, "[SILENCIO_MODO_MANUAL]", estado, calificado)
            return 
            
        print(f"📊 {prefix} [ESTADO ANTERIOR] {estado}")

        txt_lower = texto_unificado.lower()

        # 🔥 PARCHE: SI CONTESTAN AL SEGUIMIENTO, LOS METEMOS AL EMBUDO
        if estado == "SEGUIMIENTO":
            estado = "ESPERA_DATOS"

        # 🔥 BOTÓN DE REINICIO ("EMPEZAR")
        if len(texto_unificado.split()) < 3 and "empezar" in txt_lower:
            estado = "NUEVO"

        # 🛡️ ESCENARIO 2: MURO ANTI-TROLL DIRECTO 
        palabras_rechazo = ["putos", "no quiero", "deja de molestar", "ya soy telcel", "soy telcel", "cancelar", "chinga", "pendejo"]
        if any(p in txt_lower for p in palabras_rechazo):
            print(f"🛑 {prefix} [RECHAZO/TROLL] Cliente descartado.")
            resp = "Entendido, gracias por tu tiempo. Si en algún momento deseas aprovechar las promociones, aquí estaremos. ¡Que tengas un excelente día! 👋"
            update_sesion_sql(telefono, "FIN", data, calificado, campana_detectada, num_portar_sql, None)
            enviar_mensaje(telefono, resp)
            log_mensaje_sql(telefono, texto_unificado, resp, "FIN", calificado)
            return

        # 🛡️ ESCENARIO 3: MENSAJE CORTO O EMOJI
        if len(texto_unificado.strip()) <= 2 and not any(x in txt_lower for x in ["si", "sí", "ok", "va", "ya"]):
            print(f"⚠️ {prefix} Mensaje demasiado corto o solo emoji. Ignorando para no ciclar.")
            log_mensaje_sql(telefono, texto_unificado, "[SILENCIO_MENSAJE_CORTO]", estado, calificado)
            return

        historial_previo = get_historial_chat(telefono)

        SYSTEM_PROMPT = f"""
        ### INSTRUCCIONES DE IDENTIDAD Y VENTAS
        Eres MIA, la asistente virtual experta en ventas de Portabilidad Telcel.
        El cliente se llama: "{nombre}". Úsalo de forma natural UNA SOLA VEZ en tu respuesta para empatizar. NUNCA lo repitas en cada mensaje.
        Tu objetivo principal es conseguir el NÚMERO A 10 DÍGITOS del cliente de forma sutil y persuasiva.

        ### BASE DE CONOCIMIENTOS
        <contexto>
        {KB_TEXTO}
        </contexto>
        
        <promociones>
        {PROMO_TXT}
        </promociones>
        
        <faq>
        {FAQ_TEXTO}
        </faq>
        
        ### REGLAS DE ORO (V66):
        1. **BREVEDAD SEXTA:** Máximo 2 oraciones. Si hablas mucho, el cliente se va.
        2. **FILTRO REGIONAL:** El beneficio SOLO aplica para Puebla, Veracruz, Oaxaca, Guerrero y Tlaxcala (R7). 
        3. **PIVOTE YA TELCEL:** Si el cliente dice que ya es Telcel, dile: "¡Qué bien! Esta promo es para líneas nuevas. ¿Me pasas el número de un familiar (AT&T/Movistar) para activarle el regalo a ellos? 🎁"
        4. **GANCHO + CIERRE:** Responde dudas mencionando el regalo (5.5GB + Redes + Chip Gratis) y remata con: "¿Me compartes tu número a 10 dígitos para ver si tu línea califica?"
        5. **CIERRE CONDICIONADO:** Usa: "Para que el sistema me permita activarte el regalo de San Valentín, necesito checar tu número..."
        6. **MATAR OBJECIONES:** El trámite es GRATIS, conservas tu número y no te quedas sin señal. ¿Cuál es tu número para apartar tu lugar?
        7. **SENTIDO DE URGENCIA:** Los folios de regalo son limitados por hoy. ¡Aprovecha! ✅
        
        """

        resp, prox_estado = "", estado
        nuevo_calificado = calificado
        agenda_sql = None

        if estado == "NUEVO":
            # 🔥 RASTREO TEMPRANO: Inyectamos el teléfono de la conversación de inmediato
            tel_conversacion = telefono[-10:] if len(telefono) >= 10 else telefono
            insertar_referido(tel_conversacion, tipo_insercion="Chat Temprano")

            es_saludo = len(texto_unificado.split()) < 6 and any(x in txt_lower for x in ["hola", "buenas", "info", "interesa", "precio", "hey", "que tal", "holandas"])
            if es_saludo:
                resp = (f"¡Hola {nombre}! 👋 Soy MIA, tu asistente de Telcel.\n\n{PROMO_SHORT}\n\n¿Te gustaría que te explique a detalle los beneficios o prefieres que validemos si tu línea aplica? 😊") 
            else:
                prompt_gemini = f"{SYSTEM_PROMPT}\nHISTORIAL: {historial_previo}\nMENSAJE DEL CLIENTE: '{texto_unificado}'\nINSTRUCCIÓN: Responde aplicando las reglas."
                
                prompt_para_log = prompt_gemini.replace(KB_TEXTO, "[...TXT BD OCULTO...]").replace(PROMO_TXT, "[...TXT PROMOS OCULTO...]").replace(FAQ_TEXTO, "[...TXT FAQ OCULTO...]")
                print(f"\n🧠 [DEBUG IA - LEYENDO MENTE DE MIA (ESTADO: NUEVO)]")
                print(f"Enviando contexto a Gemini:\n{prompt_para_log}\n")
                
                try: 
                    gen_response = model.generate_content(prompt_gemini)
                    resp = gen_response.text.strip()
                    print(f"💭 [DEBUG IA - RESPUESTA CRUDA]: {resp}\n")
                except Exception as e: 
                    print(f"❌ ERROR REAL DE GEMINI: {e}")
                    resp = f"¡Hola {nombre}! {PROMO_SHORT} ¿Te gustaría conocer los beneficios?"
                    
            prox_estado = "ESPERA_DATOS"
            update_sesion_sql(telefono, prox_estado, data, 0, campana_detectada)

        elif estado == "ESPERA_DATOS":
            solo_nums = re.sub(r'\D', '', texto_unificado)
            tel_final = ""
            if len(solo_nums) == 10:
                tel_final = solo_nums
            else:
                match = re.search(r'\b\d{10}\b', texto_unificado)
                if match: tel_final = match.group(0)

            if tel_final:
                print(f"✅ {prefix} [NUMERO VALIDO] {tel_final}")
                num_portar_sql = tel_final
                nuevo_calificado = 1
                insertar_referido(tel_final, tipo_insercion="A Portar")
                resp = f"✅ ¡Perfecto! He registrado el {tel_final}. Recibirás una llamada desde el número: {NUMERO_LLAMADA}, en cuanto un agente esté disponible."
                agenda_sql = "En cola de espera"
                prox_estado = "ESPERA_CONFIRMACION_HORARIO" 
            else:
                if len(solo_nums) >= 7 and len(solo_nums) != 10: 
                    resp = f"⚠️ El número parece incompleto. Por favor escribe tu número a 10 dígitos exactos."
                elif any(x in txt_lower for x in ["no puedo", "ocupado", "luego", "mas tarde", "mañana", "ahorita no", "trabajando", "noche"]):
                     resp = (f"¡No te preocupes! 😉 Podemos marcarte más tarde.\n\nSolo recuerda que el trámite es súper rápido y tienes beneficios increíbles 🎁\n\n¿Te parece si me dejas tu número a 10 dígitos y agendamos para luego? 📞")
                else:
                    palabras_afirmativas = [ "sí", "claro", "adelante", "va", "me late", "bueno", "ok", "esta bien", "me interesa", "si", "simon", "sipi" ]
                    es_afirmativo = any(p in txt_lower.split() for p in palabras_afirmativas) or any(emoji in texto_unificado for emoji in ["👍", "👌", "🔥", "😉", "😊"])
                    
                    if es_afirmativo:
                        resp = f"¡Excelente elección! 🎉 Para revisar en sistema si tu línea aplica a la promoción, por favor compárteme tu **número a 10 dígitos**."
                    else:
                        prompt_gemini = f"""
                        {SYSTEM_PROMPT}
                        
                        HISTORIAL DE LA CONVERSACIÓN:
                        {historial_previo}
                        
                        MENSAJE ACTUAL DEL CLIENTE: '{texto_unificado}'
                        
                        INSTRUCCIÓN ESPECÍFICA: El cliente aún no da su número, parece tener una duda, curiosidad o está saludando. 
                        Aplica neuroventas: primero empatiza, resuelve su duda o devuélvele el saludo con mucha energía, y al final usa el 'Cierre Condicionado' para pedir el número a 10 dígitos sutilmente. No suenes como robot.
                        """
                        
                        prompt_para_log = prompt_gemini.replace(KB_TEXTO, "[...TXT BD OCULTO...]").replace(PROMO_TXT, "[...TXT PROMOS OCULTO...]").replace(FAQ_TEXTO, "[...TXT FAQ OCULTO...]")
                        print(f"\n🧠 [DEBUG IA - LEYENDO MENTE DE MIA (ESTADO: ESPERA_DATOS)]")
                        print(f"Enviando contexto a Gemini:\n{prompt_para_log}\n")

                        try:
                            gen_response = model.generate_content(prompt_gemini)
                            resp = gen_response.text.strip()
                            print(f"💭 [DEBUG IA - RESPUESTA CRUDA]: {resp}\n")
                        except Exception as e:
                            print(f"❌ ERROR REAL DE GEMINI: {e}")
                            resp = f"¡Esa es una excelente pregunta! 🤔 Un agente humano te la puede resolver a detalle en una llamada súper rápida. ¿Me indicas tu número a 10 dígitos para marcarte, por favor? 👉"
                
                prox_estado = "ESPERA_DATOS"

        elif estado == "ESPERA_CONFIRMACION_HORARIO":
            if any(x in txt_lower for x in ["no", "ocupado", "trabajo", "otra hora", "mañana", "luego", "ahorita no"]):
                resp = (f"¡Entendido! 😉 Podemos marcarte más tarde.\n\nSolo recuerda que el trámite es rápido y te llevas 5.5GB + Redes 🎁\n\nSelecciona una hora aquí 👇")
                enviar_lista_horarios(telefono, "Agendar para luego:")
                prox_estado = "ESPERA_SELECCION_LISTA"
                update_sesion_sql(telefono, prox_estado, data, nuevo_calificado, None, num_portar_sql)
                return 
            else:
                numero_mostrar = num_portar_sql if num_portar_sql else "tu número"
                resp = f"¡Excelente! Un agente te llamará al {numero_mostrar} en breve. La llamada la realizaremos desde el número: {NUMERO_LLAMADA}. 👋"
                prox_estado = "FIN"

        elif estado == "ESPERA_SELECCION_LISTA":
            if any(op in texto_unificado for op in RANGOS_LISTA) or "rango_" in txt_lower:
                resp = f"✅ Quedó agendado: {texto_unificado}."
                agenda_sql = texto_unificado
                prox_estado = "FIN"
            else:
                resp = f"Por favor selecciona una opción válida de la lista 👇"
                enviar_lista_horarios(telefono, "Intenta de nuevo:")
                prox_estado = "ESPERA_SELECCION_LISTA"
                update_sesion_sql(telefono, prox_estado, data, nuevo_calificado, None, num_portar_sql)
                return

        elif estado == "FIN":
            prompt_gemini = f"{SYSTEM_PROMPT}\nHISTORIAL: {historial_previo}\nCLIENTE: '{texto_unificado}'\nINSTRUCCIÓN: Despedida amable y muy breve."
            
            prompt_para_log = prompt_gemini.replace(KB_TEXTO, "[...TXT BD OCULTO...]").replace(PROMO_TXT, "[...TXT PROMOS OCULTO...]").replace(FAQ_TEXTO, "[...TXT FAQ OCULTO...]")
            print(f"\n🧠 [DEBUG IA - LEYENDO MENTE DE MIA (ESTADO: FIN)]")
            print(f"Enviando contexto a Gemini:\n{prompt_para_log}\n")
            
            try: 
                gen_response = model.generate_content(prompt_gemini)
                resp = gen_response.text.strip()
                print(f"💭 [DEBUG IA - RESPUESTA CRUDA]: {resp}\n")
            except Exception as e: 
                print(f"❌ ERROR REAL DE GEMINI: {e}")
                resp = f"Gracias {nombre}. ¡Hasta pronto! 👋"
                
            prox_estado = "FIN"
            
        else: resp, prox_estado = "", "NUEVO"

        # 🔥 ACTUALIZACIÓN FINAL DE ESTADO
        update_sesion_sql(telefono, prox_estado, data, nuevo_calificado, None, num_portar_sql, agenda_sql)
        
        # 🔥 ENVÍO A META
        if resp: 
            print(f"🤖 {prefix} [MIA RESPONDE] {resp}")
            enviar_mensaje(telefono, resp)
            
        # 🛡️ ESCENARIO 4: LOG GARANTIZADO SIEMPRE (Pase lo que pase)
        log_mensaje_sql(telefono, texto_unificado, resp if resp else "[SILENCIO_SIN_RESPUESTA]", estado, nuevo_calificado)

    except Exception as e:
        print(f"❌❌ {prefix if 'prefix' in locals() else '[ERROR]'} {e}")
        import traceback
        traceback.print_exc()
        
        # 🛡️ ESCENARIO 5: ERROR CRÍTICO (El código explotó, pero el mensaje del cliente SE GUARDA)
        try:
            log_mensaje_sql(telefono, texto_unificado, f"[ERROR_INTERNO_MIA]", "ERROR", 0)
        except:
            pass # Si el error fue que la BD se desconectó, aquí ya no podemos hacer nada.

# ==========================================
# 5. SERVER WEB (WEBHOOKS) CON TRACKER META
# ==========================================
@app.route('/webhook', methods=['POST'])
def recibir_mensaje():
    try:
        body = request.get_json()
        print(f"\n📥 [INCOMING] Payload recibido:\n{json.dumps(body, indent=2)}")

        if 'entry' not in body or not body['entry']:
            return jsonify({"status": "ignored"}), 200

        entry = body['entry'][0]

        if 'changes' in entry and len(entry['changes']) > 0:
            value = entry['changes'][0].get('value', {})
            
            if 'messages' in value and len(value['messages']) > 0:
                msg = value['messages'][0]
                tel = msg['from']
                
                try: nom = value['contacts'][0]['profile']['name']
                except: nom = "Amigo"
                
                type_msg = msg.get('type', '')
                txt = ""
                campana_detectada = "organico"

                # 🔥 EL CAZADOR DE ANUNCIOS (META TRACKER V60) 🔥
                if 'referral' in msg:
                    ref = msg['referral']
                    # Busca 'headline', si no existe, toma los primeros 40 chars del 'body'
                    ad_text = ref.get('headline') or ref.get('body', 'Campaña Meta')
                    if len(ad_text) > 40:
                        ad_text = ad_text[:37] + "..."
                    
                    # Busca 'ad_id', si no existe, toma 'source_id'
                    ad_id = ref.get('source_id') or ref.get('ad_id', 'Desconocido')
                    
                    campana_detectada = f"MetaAd | {ad_text} | ID:{ad_id}"
                    print(f"📢 [MARKETING TRACKER] Lead detectado: {campana_detectada}")
                
                if type_msg == 'text': 
                    txt = msg['text']['body']
                elif type_msg == 'interactive':
                    if 'button_reply' in msg['interactive']: 
                        txt = msg['interactive']['button_reply']['title']
                    elif 'list_reply' in msg['interactive']: 
                        txt = msg['interactive']['list_reply']['title']
                        
                # 🔥 PARCHE V63: MIA LEE TARJETAS DE CONTACTO (Y SE IGNORA A SÍ MISMA) 🔥
                elif type_msg == 'contacts':
                    try:
                        # Usamos 'wa_id' porque Meta ya te lo entrega solo con números limpios
                        numero_compartido = msg['contacts'][0]['phones'][0]['wa_id']
                        
                        # Candado: Verificamos si la tarjeta es la de MIA
                        if NUMERO_LLAMADA in numero_compartido:
                            print(f"⚠️ [CONTACTO IGNORADO] El cliente compartió la tarjeta de MIA.")
                            txt = "" # Al dejar 'txt' vacío, MIA ignora la acción por completo.
                        else:
                            txt = numero_compartido
                            print(f"📇 [CONTACTO RECIBIDO] Se extrajo el número: {txt}")
                    except Exception as e:
                        txt = "Te compartí un contacto"
                
                if txt:
                    logging.info(f"📩 {nom}: {txt}") 
                    if tel in active_timers: active_timers[tel].cancel()
                    if tel not in message_buffers: message_buffers[tel] = []
                    message_buffers[tel].append(txt)
                    
                    t = threading.Timer(3.0, ejecutar_logica_batch, args=[tel, message_buffers[tel], nom, campana_detectada])
                    t.start()
                    active_timers[tel] = t

        return jsonify({"status": "ok"}), 200
    except Exception as e: 
        print(f"❌ Error Webhook: {e}")
        return jsonify({"status": "error"}), 200

@app.route('/webhook', methods=['GET'])
def verificar():
    if request.args.get("hub.verify_token") == VERIFY_TOKEN: return request.args.get("hub.challenge")
    return "Error", 403

# ==========================================
# 6. RUTAS DEL DASHBOARD
# ==========================================
@app.route('/webhook/heartbeat', methods=['GET'])
def heartbeat():
    cpu_usage = psutil.cpu_percent(interval=None)
    ram = psutil.virtual_memory()
    health_data = {
        "bot": "MIA WhatsApp V62",
        "status": "Online",
        "timestamp": datetime.now().isoformat(),
        "system": {
            "cpu_percent": cpu_usage,
            "ram_percent": ram.percent,
            "ram_free_gb": round(ram.available / (1024**3), 2),
            "os": platform.system(),
            "threads": threading.active_count()
        }
    }
    if cpu_usage > 90:
        health_data["status"] = "Warning - High CPU"
    return health_data, 200

@app.route('/dashboard')
@requires_auth 
def dashboard():
    return render_template('dashboard.html')

@app.route('/enviar_manual', methods=['POST'])
@requires_auth 
def enviar_manual():
    try:
        d = request.get_json()
        telefono = d['telefono']
        texto = d['texto']
        
        enviar_mensaje(telefono, texto)
        log_mensaje_sql(telefono, "[INTERVENCION_HUMANA]", texto, "MANUAL", 1)
        
        conn = pyodbc.connect(SQL_CONN_STR)
        cursor = conn.cursor()
        cursor.execute("UPDATE tb_mia_flujo_ventas SET modo_manual = 1, ultima_interaccion = GETDATE() WHERE telefono = ?", (telefono,))
        conn.commit()
        conn.close()
        
        print(f"🛑 [MODO MANUAL] Activado para {telefono}. MIA no responderá más.")
        return jsonify({"status": "ok", "modo": "manual"})
    except Exception as e: 
        return jsonify({"error": str(e)}), 500

# ==========================================
# ⚡ RUTA DE CHATS (TURBO OPTIMIZADA CON TU VISTA)
# ==========================================
@app.route('/api/chats')
@requires_auth 
def api_chats():
    try:
        conn = pyodbc.connect(SQL_CONN_STR)
        cursor = conn.cursor()
        
        search_term = request.args.get('q', '').strip()
        filtro_extra = ""
        params = []

        if search_term:
            if re.match(r'^\d+$', search_term):
                filtro_extra = " AND telefono_conversacion LIKE ? "
                params.append(f"%{search_term}%")
            else:
                filtro_extra = " AND telefono_conversacion IN (SELECT DISTINCT telefono FROM tb_mia_logs_mensajes WITH (NOLOCK) WHERE mensaje_usuario LIKE ? OR respuesta_bot LIKE ?) "
                params.append(f"%{search_term}%")
                params.append(f"%{search_term}%")

        # 🔥 CONSULTA OPTIMIZADA: Solo los 500 más recientes de TU VISTA
        query = f"""
        SELECT TOP 500 *
        FROM dbo.vw_resumen_numeros_mia 
        WHERE 1=1 {filtro_extra}
        ORDER BY ultima_interaccion DESC
        """
        
        cursor.execute(query, params)
        
        # Leemos dinámicamente los nombres de las columnas
        columnas = [column[0].lower() for column in cursor.description]
        chats = []
        ahora = datetime.now()
        
        for row in cursor.fetchall():
            r = dict(zip(columnas, row)) 
            
            tel = r.get('telefono_conversacion') or r.get('telefono', '')
            ultima_fecha = r.get('ultima_interaccion')
            
            ventana_abierta = False
            if ultima_fecha:
                diff = ahora - ultima_fecha
                if diff.total_seconds() < (24 * 3600): ventana_abierta = True
            
            fecha_str = ultima_fecha.strftime("%d/%m %H:%M") if ultima_fecha else "Nuevo"
            
            f_estatus = r.get('fecha_estatus') or r.get('fechaestatus')
            f_estatus_str = f_estatus.strftime("%d/%m") if hasattr(f_estatus, 'strftime') else "-"

            # 🔥 BLINDAJE DE ESTATUS: Si viene NULL de SQL, lo transformamos para que el HTML no se rompa.
            est_ok = r.get('estatus_ok')
            est_conv = r.get('estatus_telefono_conversacion')

            estatus_ok_limpio = str(est_ok).strip() if est_ok else '-'
            estatus_conv_limpio = str(est_conv).strip() if est_conv else 'SIN BARRER'

            chats.append({
                "telefono": tel,
                "fecha": fecha_str,
                "estado": "MANUAL" if r.get('modo_manual') == 1 else r.get('estado_actual', ''),
                
                # Inyectamos los textos ya protegidos
                "estatus_ok": estatus_ok_limpio if estatus_ok_limpio not in ('None', '') else '-', 
                "estatus_conversacion": estatus_conv_limpio if estatus_conv_limpio not in ('None', '') else 'SIN BARRER', 
                
                "calificado": 0, 
                "ventana_24h": ventana_abierta,
                "comentarios": r.get('comentarios', ''), 
                "info_portabilidad": {
                    "numero_portar": r.get('numero_a_portar', '-'), 
                    "estatus": r.get('estatus', '-'), 
                    "fecha_estatus": f_estatus_str, 
                    "lugar": r.get('lugar', '-')
                }
            })
            
        conn.close()
        return jsonify(chats)

    except Exception as e: 
        print(f"\n❌ ERROR VISTA: {e}")
        return jsonify([])




@app.route('/api/historial/<telefono>')
def api_historial(telefono):
    try:
        conn = pyodbc.connect(SQL_CONN_STR)
        cursor = conn.cursor()
        query = """
        SELECT mensaje_usuario, respuesta_bot, estado_en_ese_momento, fecha_registro 
        FROM tb_mia_logs_mensajes WITH (NOLOCK)
        WHERE telefono = ? 
        ORDER BY fecha_registro ASC
        """
        cursor.execute(query, (telefono,))
        logs = []
        for row in cursor.fetchall():
            fecha_full = row[3].strftime("%d/%m %H:%M") 
            logs.append({
                "mensaje_usuario": row[0],
                "respuesta_bot": row[1],
                "estado": row[2],
                "fecha": fecha_full 
            })
        conn.close()
        return jsonify(logs)
    except Exception as e: 
        return jsonify([])

@app.route('/api/reactivar/<telefono>', methods=['POST'])
def reactivar_bot(telefono):
    try:
        conn = pyodbc.connect(SQL_CONN_STR)
        cursor = conn.cursor()
        cursor.execute("UPDATE tb_mia_flujo_ventas SET modo_manual = 0 WHERE telefono = ?", (telefono,))
        conn.commit()
        conn.close()
        print(f"🟢 [MODO AUTO] Reactivado para {telefono}. MIA vuelve al control.")
        return jsonify({"status": "ok"})
    except: 
        return jsonify({"error": "fail"}), 500

@app.route('/api/guardar_comentario', methods=['POST'])
@requires_auth
def guardar_comentario():
    try:
        d = request.get_json()
        telefono = d.get('telefono')
        comentario = d.get('comentario')
        
        conn = pyodbc.connect(SQL_CONN_STR)
        cursor = conn.cursor()
        cursor.execute("UPDATE tb_mia_flujo_ventas SET comentarios = ? WHERE telefono = ?", (comentario, telefono))
        conn.commit()
        conn.close()
        
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print(f"🚀 MIA V62 ONLINE Y LISTA PARA VENDER")
    t_seguimiento = threading.Thread(target=hilo_seguimiento)
    t_seguimiento.daemon = True 
    t_seguimiento.start()
    
    # 🔥 THREADED=TRUE: Elimina el lag de clics concurrentes
    app.run(port=5000, debug=True, use_reloader=False, threaded=True)