from flask import Blueprint, request, jsonify
import json
import logging
import threading
from config import VERIFY_TOKEN, NUMERO_LLAMADA
from services.logic import ejecutar_logica_batch

webhook_bp = Blueprint('webhook', __name__)

message_buffers = {} 
active_timers = {}   

@webhook_bp.route('/webhook', methods=['GET'])
def verificar():
    if request.args.get("hub.verify_token") == VERIFY_TOKEN: 
        return request.args.get("hub.challenge")
    return "Error", 403

@webhook_bp.route('/webhook', methods=['POST'])
def recibir_mensaje():
    try:
        body = request.get_json()
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

                if 'referral' in msg:
                    ref = msg['referral']
                    ad_text = ref.get('headline') or ref.get('body', 'Campaña Meta')
                    if len(ad_text) > 40: ad_text = ad_text[:37] + "..."
                    ad_id = ref.get('source_id') or ref.get('ad_id', 'Desconocido')
                    campana_detectada = f"MetaAd | {ad_text} | ID:{ad_id}"
                
                if type_msg == 'text': 
                    txt = msg['text']['body']
                elif type_msg == 'interactive':
                    if 'button_reply' in msg['interactive']: 
                        txt = msg['interactive']['button_reply']['title']
                    elif 'list_reply' in msg['interactive']: 
                        txt = msg['interactive']['list_reply']['title']
                elif type_msg == 'contacts':
                    try:
                        numero_compartido = msg['contacts'][0]['phones'][0]['wa_id']
                        if NUMERO_LLAMADA in numero_compartido:
                            txt = "" 
                        else:
                            txt = numero_compartido
                    except:
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
