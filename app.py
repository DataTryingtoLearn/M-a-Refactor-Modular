from flask import Flask
from routes.webhooks import webhook_bp
from routes.api import api_bp
from routes.dashboard import dashboard_bp
from services.scheduler import start_scheduler
from logger import setup_logger

app = Flask(__name__)

# Register Blueprints
app.register_blueprint(webhook_bp)
app.register_blueprint(api_bp)  # Prefixes are now inside the blueprint routes or matching dashboard
app.register_blueprint(dashboard_bp)

if __name__ == '__main__':
    setup_logger()
    print("🚀 MIA Modular System Starting...")
    start_scheduler()
    app.run(port=5000, debug=True, use_reloader=False, threaded=True)
