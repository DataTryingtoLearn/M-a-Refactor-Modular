import time
import random
import pytz
import threading
from datetime import datetime
from database import get_connection, log_mensaje_sql
from services.meta import enviar_mensaje

def hilo_seguimiento():
    print("🕵️‍♂️ [SEGUIMIENTO] Iniciado.")
    
    MSGS_CANDIDATO = [
        "👀 ¡Hola! Noté que no terminamos tu registro. ¿Todo bien? Recuerda que tienes 5.5GB + Redes esperando 🎁.",
        "👋 ¿Sigues ahí? Solo te recuerdo que el trámite es 100% GRATIS y rápido. ¿Te ayudo a terminar? 👇",
        "⚠️ Último aviso: Tu promoción de 5.5GB está por expirar. ¿Quieres aprovecharla antes de que se vaya? 🚀",
        "💌 ¡Por el mes del amor y la amistad! 💘 No olvides que podrías llevarte tu primera recarga GRATIS. Déjame tu número a 10 dígitos para validarlo 😁👇"
    ]

    MSGS_TELCEL = [
        "💙 ¡Hola! Vi que tu línea ya es Telcel. ¡Qué bueno que eres parte de la familia! ¿Me pasas el número de un familiar para activarle el regalo a ellos? 🎁✨",
        "👋 ¡No te quedes sin tu recarga gratis!! Aunque tú seas Telcel, puedes dárselo a alguien más. 👇"
    ]

    MSGS_REGION = [
        "📍 ¡Hola! Noté que tu zona está fuera de nuestra cobertura. ¿Tienes algún familiar viviendo en Puebla, Veracruz, Oaxaca, Guerrero o Tlaxcala para pasarle el beneficio? 🎁",
        "⚠️ Solo recordándote que tu recarga gratis es exclusiva para R7. Si tienes un número de esa zona, pásamelo. 👇"
    ]

    zona_mexico = pytz.timezone('America/Mexico_City')

    while True:
        try:
            ahora_mexico = datetime.now(zona_mexico)
            if 8 <= ahora_mexico.hour < 22:
                with get_connection() as conn:
                    cursor = conn.cursor()
                    query = """
                    SELECT telefono_conversacion, ISNULL(intentos_seguimiento, 0), estatus_telefono_conversacion
                    FROM dbo.vw_resumen_numeros_mia WITH (NOLOCK)
                    WHERE numero_a_portar IS NULL 
                    AND estado_actual NOT IN ('FIN', 'MANUAL')
                    AND DATEDIFF(minute, ultima_interaccion, GETDATE()) > 60 
                    AND fecha_ultimo_mensaje IS NOT NULL
                    AND DATEDIFF(hour, fecha_ultimo_mensaje, GETDATE()) < 23
                    """
                    cursor.execute(query)
                    rows = cursor.fetchall()

                if rows:
                    print(f"🕵️‍♂️ [SEGUIMIENTO] Procesando {len(rows)} leads...")

                for r in rows:
                    tel = r[0]
                    intentos = int(r[1])
                    status_chat = str(r[2]).upper()
                    
                    lista_actual = MSGS_CANDIDATO
                    max_intentos_permitidos = 4

                    if status_chat == 'YA ES TELCEL':
                        lista_actual = MSGS_TELCEL
                        max_intentos_permitidos = 2
                    elif status_chat == 'FUERAREGION':
                        lista_actual = MSGS_REGION
                        max_intentos_permitidos = 2
                    
                    if intentos >= max_intentos_permitidos:
                        continue

                    time.sleep(random.uniform(60, 90))

                    try:
                        with get_connection() as conn_check:
                            cursor_check = conn_check.cursor()
                            cursor_check.execute("SELECT count(*) FROM tb_mia_flujo_ventas WHERE telefono = ? AND DATEDIFF(minute, ultima_interaccion, GETDATE()) < 5", (tel,))
                            if cursor_check.fetchone()[0] > 0:
                                continue 
                            
                            texto_enviar = lista_actual[intentos]
                            print(f"🚀 [ENVIANDO SEGUIMIENTO] A {tel} | Intento: {intentos + 1}")
                            
                            if enviar_mensaje(tel, texto_enviar):
                                cursor_check.execute("""
                                    UPDATE tb_mia_flujo_ventas 
                                    SET intentos_seguimiento = ?, ultima_interaccion = GETDATE(), estado_actual = 'SEGUIMIENTO' 
                                    WHERE telefono = ?
                                """, (intentos + 1, tel))
                                conn_check.commit()
                                log_mensaje_sql(tel, "[AUTO_SEGUIMIENTO]", texto_enviar, "SEGUIMIENTO", 0)

                    except Exception as e_inner:
                        print(f"❌ Error seguimiento individual {tel}: {e_inner}")

            time.sleep(900) 
        except Exception as e:
            print(f"❌ [ERROR SEGUIMIENTO]: {e}")
            time.sleep(600) 

def start_scheduler():
    t = threading.Thread(target=hilo_seguimiento)
    t.daemon = True
    t.start()
    return t
