import os
from dotenv import load_dotenv

load_dotenv('.Env')

# Basic Config
NUMERO_LLAMADA = os.getenv("NUMERO_LLAMADA", "2292349024")
DIAS_REINICIO = float(os.getenv("DIAS_REINICIO", 1.0))
HISTORY_LIMIT = int(os.getenv("HISTORY_LIMIT", 5))
RANGOS_AGENDA = [x.strip() for x in os.getenv("RANGOS_AGENDA", "09-11 AM,11-01 PM,04-06 PM,Despues 06 PM").split(',')]

# Meta Credentials
TOKEN_META = os.getenv("FACEBOOK_ACCESS_TOKEN") 
PHONE_ID = os.getenv("FACEBOOK_PHONE_NUMBER_ID") 
VERIFY_TOKEN = os.getenv("FACEBOOK_VERIFY_TOKEN", "HOLA_MIA")

# SQL Config
SQL_CONN_STR = (
    f"DRIVER={{{os.getenv('SQL_DRIVER', 'ODBC Driver 17 for SQL Server')}}};"
    f"SERVER={os.getenv('SQL_SERVER')};"
    f"DATABASE={os.getenv('SQL_DATABASE')};"
    f"UID={os.getenv('SQL_USERNAME')};"
    f"PWD={os.getenv('SQL_PASSWORD')}"
)

# Auth
USUARIOS_VALIDOS = {
    "E029973": "E029973JO", 
    "E019588": "E019588CS",
    "E029863": "E029863MM",
    "E015379": "E015379CG",
    "E041364": "E041364IG"
}

# Paths (Adjusted to be relative or safer defaults)
LOGS_DIR = os.getenv("LOGS_DIR", r"Logs")
DOCS_DIR = os.getenv("DOCS_DIR", r"Docs")

os.makedirs(LOGS_DIR, exist_ok=True)
os.makedirs(DOCS_DIR, exist_ok=True)
