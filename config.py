import os
import logging
import json
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
import pillow_heif

pillow_heif.register_heif_opener()

# Настройка логирования
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Конфигурация
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['EXAMPLES_FOLDER'] = 'static/uploads/examples'
os.makedirs(app.config['EXAMPLES_FOLDER'], exist_ok=True)

app.config['ALLOWED_EXTENSIONS'] = {
    'png', 'jpg', 'jpeg', 'gif', 'bmp', 'tiff', 'webp', 'heic', 'heif'
}

app.config['SESSION_TYPE'] = 'filesystem'
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['TEMP_FOLDER'] = 'temp_uploads'

# Создание папок
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['TEMP_FOLDER'], exist_ok=True)
os.makedirs(os.path.join('instance'), exist_ok=True)

@app.template_filter('from_json')
def from_json_filter(json_string):
    """Преобразует JSON строку в объект Python для использования в шаблонах"""
    if not json_string:
        return {}
    try:
        return json.loads(json_string)
    except (json.JSONDecodeError, TypeError):
        return {}

# Инициализация расширений
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Пожалуйста, войдите для доступа к этой странице'