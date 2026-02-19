import re
import json
from datetime import datetime
from database import (
    get_sesion_sql, update_sesion_sql, log_mensaje_sql, 
    get_historial_chat, insertar_referido
)
from services.meta import enviar_mensaje, enviar_lista_horarios
from services.ai import setup_ai, KB_TEXTO, PROMO_TXT, FAQ_TEXTO, PROMO_SHORT
from config import NUMERO_LLAMADA

model = setup_ai()

def ejecutar_logica_batch(telefono, lista_mensajes, nombre, campana_detectada):
    try:
        texto_unificado = " ".join(lista_mensajes)
        prefix = f"[{telefono}]"
        print(f"\n🚀 {prefix} [BATCH] {nombre} dice: {texto_unificado}")
        print(f"🎯 [MARKETING INFO] Fuente detectada: {campana_detectada}")
        
        sesion = get_sesion_sql(telefono)
        estado, data, calificado = sesion["state"], sesion["data"], sesion["calificado"]
        num_portar_sql = sesion["num_portar"] 
        
        if sesion["manual"] == 1: 
            print(f"⛔ {prefix} [MANUAL ACTIVADO] El humano tiene el control.")
            log_mensaje_sql(telefono, texto_unificado, "[SILENCIO_MODO_MANUAL]", estado, calificado)
            return 
            
        print(f"📊 {prefix} [ESTADO ANTERIOR] {estado}")
        txt_lower = texto_unificado.lower()

        if estado == "SEGUIMIENTO":
            estado = "ESPERA_DATOS"

        if len(texto_unificado.split()) < 3 and "empezar" in txt_lower:
            estado = "NUEVO"

        palabras_rechazo = ["putos", "no quiero", "deja de molestar", "ya soy telcel", "soy telcel", "cancelar", "chinga", "pendejo"]
        if any(p in txt_lower for p in palabras_rechazo):
            print(f"🛑 {prefix} [RECHAZO/TROLL] Cliente descartado.")
            resp = "Entendido, gracias por tu tiempo. Si en algún momento deseas aprovechar las promociones, aquí estaremos. ¡Que tengas un excelente día! 👋"
            update_sesion_sql(telefono, "FIN", data, calificado, campana_detectada, num_portar_sql, None)
            enviar_mensaje(telefono, resp)
            log_mensaje_sql(telefono, texto_unificado, resp, "FIN", calificado)
            return

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
            tel_conversacion = telefono[-10:] if len(telefono) >= 10 else telefono
            insertar_referido(tel_conversacion, tipo_insercion="Chat Temprano")

            es_saludo = len(texto_unificado.split()) < 6 and any(x in txt_lower for x in ["hola", "buenas", "info", "interesa", "precio", "hey", "que tal", "holandas"])
            if es_saludo:
                resp = (f"¡Hola {nombre}! 👋 Soy MIA, tu asistente de Telcel.\n\n{PROMO_SHORT}\n\n¿Te gustaría que te explique a detalle los beneficios o prefieres que validemos si tu línea aplica? 😊") 
            else:
                prompt_gemini = f"{SYSTEM_PROMPT}\nHISTORIAL: {historial_previo}\nMENSAJE DEL CLIENTE: '{texto_unificado}'\nINSTRUCCIÓN: Responde aplicando las reglas."
                try: 
                    gen_response = model.generate_content(prompt_gemini)
                    resp = gen_response.text.strip()
                except Exception as e: 
                    print(f"❌ ERROR GEMINI: {e}")
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
                    palabras_afirmativas = ["sí", "claro", "adelante", "va", "me late", "bueno", "ok", "esta bien", "me interesa", "si", "simon", "sipi"]
                    es_afirmativo = any(p in txt_lower.split() for p in palabras_afirmativas) or any(emoji in texto_unificado for emoji in ["👍", "👌", "🔥", "😉", "😊"])
                    
                    if es_afirmativo:
                        resp = f"¡Excelente elección! 🎉 Para revisar en sistema si tu línea aplica a la promoción, por favor compárteme tu **número a 10 dígitos**."
                    else:
                        prompt_gemini = f"{SYSTEM_PROMPT}\nHISTORIAL:\n{historial_previo}\nMENSAJE:\n'{texto_unificado}'\nINSTRUCCIÓN: El cliente aún no da su número. Empatiza y pide el número a 10 dígitos."
                        try:
                            gen_response = model.generate_content(prompt_gemini)
                            resp = gen_response.text.strip()
                        except Exception as e:
                            print(f"❌ ERROR GEMINI: {e}")
                            resp = f"¡Esa es una excelente pregunta! 🤔 ¿Me indicas tu número a 10 dígitos para marcarte y resolver todas tus dudas? 👉"
                prox_estado = "ESPERA_DATOS"

        elif estado == "ESPERA_CONFIRMACION_HORARIO":
            if any(x in txt_lower for x in ["no", "ocupado", "trabajo", "otra hora", "mañana", "luego", "ahorita no"]):
                resp = (f"¡Entendido! 😉 Podemos marcarte más tarde.\n\nSelecciona una hora aquí 👇")
                enviar_lista_horarios(telefono, "Agendar para luego:")
                prox_estado = "ESPERA_SELECCION_LISTA"
                update_sesion_sql(telefono, prox_estado, data, nuevo_calificado, None, num_portar_sql)
                return 
            else:
                numero_mostrar = num_portar_sql if num_portar_sql else "tu número"
                resp = f"¡Excelente! Un agente te llamará al {numero_mostrar} en breve. 👋"
                prox_estado = "FIN"

        elif estado == "ESPERA_SELECCION_LISTA":
            from config import RANGOS_LISTA
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
            try: 
                gen_response = model.generate_content(prompt_gemini)
                resp = gen_response.text.strip()
            except Exception as e: 
                resp = f"Gracias {nombre}. ¡Hasta pronto! 👋"
            prox_estado = "FIN"
            
        else: 
            resp, prox_estado = "", "NUEVO"

        update_sesion_sql(telefono, prox_estado, data, nuevo_calificado, None, num_portar_sql, agenda_sql)
        if resp: 
            enviar_mensaje(telefono, resp)
        log_mensaje_sql(telefono, texto_unificado, resp if resp else "[SILENCIO]", estado, nuevo_calificado)

    except Exception as e:
        print(f"❌ Error en lógica batch: {e}")
        log_mensaje_sql(telefono, texto_unificado, "[ERROR_INTERNO]", "ERROR", 0)
