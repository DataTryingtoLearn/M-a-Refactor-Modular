import requests
from config import PHONE_ID, TOKEN_META, RANGOS_LISTA

def enviar_mensaje(telefono, texto):
    url = f"https://graph.facebook.com/v19.0/{PHONE_ID}/messages"
    headers = {"Authorization": f"Bearer {TOKEN_META}", "Content-Type": "application/json"}
    data = {"messaging_product": "whatsapp", "to": telefono, "type": "text", "text": {"body": texto}}
    try:
        response = requests.post(url, headers=headers, json=data, timeout=5)
        if response.status_code == 200:
            print(f"✅ [META SEND OK] Mensaje enviado a {telefono}")
            return True
        else:
            print(f"🛑 [META SEND ERROR] {response.text}")
            return False
    except Exception as e: 
        print(f"❌ Error Conexión Meta: {e}")
        return False

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
        response = requests.post(url, headers=headers, json=data, timeout=5)
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Error enviando horarios a Meta: {e}")
        return False
