from flask import Blueprint, render_template, Response, request
from functools import wraps
from config import USUARIOS_VALIDOS

dashboard_bp = Blueprint('dashboard_page', __name__)

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not (auth.username in USUARIOS_VALIDOS and USUARIOS_VALIDOS[auth.username] == auth.password):
            return Response('Unauthorized', 401, {'WWW-Authenticate': 'Basic realm="LoginRequired"'})
        return f(*args, **kwargs)
    return decorated

@dashboard_bp.route('/dashboard')
@requires_auth 
def dashboard():
    return render_template('dashboard.html')
