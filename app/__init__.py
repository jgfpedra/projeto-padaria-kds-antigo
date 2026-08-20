import sys
import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from dotenv import load_dotenv
from urllib.parse import quote_plus

# 👇 Detecta se está rodando como .exe ou em modo dev
if getattr(sys, 'frozen', False):
    base_dir = os.path.dirname(sys.executable)  # ✅ diretório do .exe
else:
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# Caminhos de template e static continuam como estavam
template_folder = os.path.join(sys._MEIPASS if getattr(sys, '_MEIPASS', False) else os.path.join(base_dir, 'app'), 'templates')
static_folder = os.path.join(sys._MEIPASS if getattr(sys, '_MEIPASS', False) else base_dir,'app', 'static')

# 🔍 Caminho EXTERNO do .env (sempre ao lado do .exe, não embutido)
env_path = os.path.join(base_dir, '.env')
load_dotenv(dotenv_path=env_path, override=True)

print("📂 ENV PATH:", env_path)
print("🔍 DATABASE_URL =", os.getenv("DATABASE_URL"))
# Inicializa Flask
app = Flask(__name__,
            static_folder=static_folder,
            template_folder=template_folder)

app.secret_key = 'chave_secreta_segura'

# Configura banco
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Extensões
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Importações internas
from app import routes
from app.models import Usuario
from app import login_manager
from app import api_routes

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))
