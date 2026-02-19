import os
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from config import DOCS_DIR

def setup_ai():
    genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
    safety_settings = {
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE, 
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE, 
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE, 
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE
    }
    model = genai.GenerativeModel(
        "gemini-2.0-flash", # Updated to a more standard name or keep as in original
        generation_config={"temperature": 0.3}, 
        safety_settings=safety_settings
    )
    return model

def leer_txt(nombre_archivo): 
    try: 
        if not nombre_archivo: return ""
        # Using configured DOCS_DIR
        ruta_completa = os.path.join(DOCS_DIR, nombre_archivo)
        if not os.path.exists(ruta_completa):
            # Fallback if the user hasn't moved files yet or for testing
            return ""
        with open(ruta_completa, 'r', encoding='utf-8') as archivo: 
            return archivo.read()
    except Exception as e: 
        print(f"⚠️ [FILE ERROR] No se pudo leer {nombre_archivo}: {e}")
        return "" 

# Initial context data
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
