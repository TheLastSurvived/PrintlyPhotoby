import os
import zipfile
from io import BytesIO
from PIL import Image
import pillow_heif
import imghdr
pillow_heif.register_heif_opener()
from flask import (
    Flask, render_template, request, redirect, url_for, 
    flash, jsonify, send_file, abort, session
)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin, login_user, login_required, 
    logout_user, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import uuid
import logging
import time
import tempfile
import json
from datetime import datetime, timedelta

# Настройка логирования
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Конфигурация
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

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

# Инициализация расширений
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Пожалуйста, войдите для доступа к этой странице'

# Модели базы данных
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(20), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    full_name = db.Column(db.String(100))
    email = db.Column(db.String(100))
    is_admin = db.Column(db.Boolean, default=False)
    sms_consent = db.Column(db.Boolean, default=False)
    privacy_consent = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    orders = db.relationship('Order', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(20), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipient_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    delivery_method = db.Column(db.String(20), nullable=False)  # belpost, europost
    delivery_details = db.Column(db.Text, nullable=False)  # JSON с деталями доставки
    total_amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, printing, ready, shipped, completed, cancelled
    tracking_number = db.Column(db.String(50))
    notes = db.Column(db.Text)
    can_edit_until = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    items = db.relationship('OrderItem', backref='order', lazy=True, cascade='all, delete-orphan')
    photos = db.relationship('OrderPhoto', backref='order', lazy=True, cascade='all, delete-orphan')

    def generate_order_number(self):
        return f"ORD-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    format_name = db.Column(db.String(50), nullable=False)
    format_size = db.Column(db.String(20), nullable=False)
    price_per_item = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    subtotal = db.Column(db.Float, nullable=False)

class OrderPhoto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    saved_filename = db.Column(db.String(255), nullable=False)
    file_size = db.Column(db.Integer)
    format = db.Column(db.String(50))  # Какой формат для этой фотографии
    file_path = db.Column(db.String(500))

class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    user_name = db.Column(db.String(100))
    rating = db.Column(db.Integer, nullable=False)  # 1-5
    text = db.Column(db.Text, nullable=False)
    is_approved = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.now)

class Discount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    discount_percent = db.Column(db.Integer, nullable=False)
    min_order_amount = db.Column(db.Float, default=0)
    valid_until = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)
    usage_limit = db.Column(db.Integer)
    used_count = db.Column(db.Integer, default=0)

class Lottery(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    prize = db.Column(db.String(200))
    start_date = db.Column(db.DateTime)
    end_date = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)
    participants = db.relationship('LotteryParticipant', backref='lottery', lazy=True)

class LotteryParticipant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lottery_id = db.Column(db.Integer, db.ForeignKey('lottery.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    phone = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.now)

class SiteContent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

class TempUpload(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(100), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    saved_filename = db.Column(db.String(255), nullable=False)
    file_size = db.Column(db.Integer)
    file_format = db.Column(db.String(50))
    format_index = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.now)

# Вспомогательные функции
def allowed_file(filename):
    allowed = app.config['ALLOWED_EXTENSIONS']
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed

def convert_to_jpg(image_path, output_path, quality=95):
    """Конвертирует изображение в JPG с сохранением качества"""
    try:
        # Проверяем формат файла
        file_ext = os.path.splitext(image_path)[1].lower()
        
        # Для HEIC/HEIF файлов используем pillow_heif
        if file_ext in ['.heic', '.heif']:
            heif_file = pillow_heif.read_heif(image_path)
            img = Image.frombytes(
                heif_file.mode, 
                heif_file.size, 
                heif_file.data,
                "raw",
                heif_file.mode,
                heif_file.stride,
            )
        else:
            img = Image.open(image_path)
        
        # Конвертируем в RGB если нужно
        if img.mode in ('RGBA', 'LA', 'P'):
            rgb_img = Image.new('RGB', img.size, (255, 255, 255))
            # Пробуем использовать альфа-канал для прозрачности
            if img.mode == 'RGBA':
                rgb_img.paste(img, mask=img.split()[-1])
            else:
                rgb_img.paste(img)
            img = rgb_img
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Сохраняем с высоким качеством
        img.save(output_path, 'JPEG', quality=quality, optimize=True)
        return True
    except Exception as e:
        print(f"Error converting image {image_path}: {e}")
        return False

def convert_to_jpg_bytes(image_path, quality=95):
    """
    Конвертирует изображение в JPG и возвращает BytesIO объект
    """
    try:
        logger.debug(f"Converting to bytes: {image_path}")
        
        # Определяем тип файла по расширению
        file_ext = os.path.splitext(image_path)[1].lower()
        
        # Открываем изображение
        img = None
        
        # Для HEIC/HEIF файлов используем pillow_heif
        if file_ext in ['.heic', '.heif']:
            try:
                logger.debug(f"Processing HEIC/HEIF file for zip: {image_path}")
                heif_file = pillow_heif.open_heif(image_path)
                
                # Конвертируем в PIL Image
                img = Image.frombytes(
                    heif_file.mode,
                    heif_file.size,
                    heif_file.data,
                    "raw",
                    heif_file.mode,
                    heif_file.stride,
                )
                
                # Проверяем на наличие информации о повороте
                if hasattr(heif_file, 'info') and 'orientation' in heif_file.info:
                    orientation = heif_file.info['orientation']
                    logger.debug(f"HEIC orientation: {orientation}")
                    if orientation == 6:
                        img = img.rotate(270, expand=True)
                    elif orientation == 8:
                        img = img.rotate(90, expand=True)
                    elif orientation == 3:
                        img = img.rotate(180, expand=True)
                        
            except Exception as e:
                logger.error(f"Error opening HEIC file: {e}")
                # Пробуем другой метод
                try:
                    img = Image.open(image_path)
                except:
                    raise
        else:
            # Для остальных форматов используем стандартный PIL
            img = Image.open(image_path)
        
        if img is None:
            raise Exception("Failed to open image")
        
        # Конвертируем в RGB если нужно
        if img.mode in ('RGBA', 'LA', 'P'):
            # Создаем белый фон для прозрачных областей
            rgb_img = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'RGBA':
                # Используем альфа-канал как маску
                rgb_img.paste(img, mask=img.split()[-1])
            elif img.mode == 'P':
                # Конвертируем палитровое изображение в RGBA, затем в RGB
                img = img.convert('RGBA')
                rgb_img.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            else:
                rgb_img.paste(img)
            img = rgb_img
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Сохраняем в BytesIO
        output = BytesIO()
        img.save(output, 'JPEG', quality=quality, optimize=True, progressive=True)
        output.seek(0)
        
        logger.debug(f"Successfully converted to JPG bytes, size: {output.getbuffer().nbytes} bytes")
        return output
        
    except Exception as e:
        logger.error(f"Error converting image to bytes {image_path}: {str(e)}", exc_info=True)
        return None

def create_zip_from_photos(order_id):
    """Создает ZIP архив с фотографиями заказа, сортируя по папкам форматов"""
    order = Order.query.get_or_404(order_id)
    zip_buffer = BytesIO()
    
    # Словарь для сопоставления индекса формата с его названием
    format_names = {
        '0': '10x15',
        '1': '10x10', 
        '2': '9x13',
        '3': 'polaroid_10x12',
        '4': 'fuji_7x10',
        '5': 'minipolaroid_7x10',
        '6': '5x15',
        'other': 'other_formats'
    }
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        # Группируем фото по форматам
        photos_by_format = {}
        
        for photo in order.photos:
            # Получаем название формата
            format_key = photo.format if photo.format else 'other'
            
            # Пытаемся получить человекочитаемое название
            if format_key.isdigit():
                format_name = format_names.get(format_key, f'format_{format_key}')
            else:
                format_name = format_names.get(format_key, format_key)
            
            if format_name not in photos_by_format:
                photos_by_format[format_name] = []
            photos_by_format[format_name].append(photo)
        
        # Также группируем по форматам из заказа (OrderItem)
        # Это нужно для соответствия между фото и форматами
        format_mapping = {}
        for idx, item in enumerate(order.items):
            format_key = str(idx)
            if item.format_name == '10x15':
                format_mapping[format_key] = '10x15'
            elif item.format_name == '10x10':
                format_mapping[format_key] = '10x10'
            elif item.format_name == '9x13':
                format_mapping[format_key] = '9x13'
            elif item.format_name == 'polaroid-10x12':
                format_mapping[format_key] = 'polaroid_10x12'
            elif item.format_name == 'fuji-7x10':
                format_mapping[format_key] = 'fuji_7x10'
            elif item.format_name == 'minipolaroid-7x10':
                format_mapping[format_key] = 'minipolaroid_7x10'
            elif item.format_name == '5x15':
                format_mapping[format_key] = '5x15'
            else:
                format_mapping[format_key] = 'other_formats'
        
        # Создаем папки и добавляем файлы
        for format_name, photos in photos_by_format.items():
            # Создаем папку для формата
            for photo in photos:
                photo_path = os.path.join(app.config['UPLOAD_FOLDER'], photo.saved_filename)
                
                if os.path.exists(photo_path):
                    try:
                        # Получаем имя файла без расширения
                        original_name = os.path.splitext(photo.original_filename)[0]
                        # Очищаем имя файла от недопустимых символов
                        original_name = secure_filename(original_name)
                        # Добавляем расширение .jpg
                        new_filename = f"{original_name}.jpg"
                        
                        # Если имя слишком длинное, укорачиваем
                        if len(new_filename) > 200:
                            new_filename = f"{original_name[:150]}.jpg"
                        
                        # Конвертируем изображение в JPG байты
                        jpg_bytes = convert_to_jpg_bytes(photo_path)
                        
                        if jpg_bytes:
                            # Добавляем в архив с путем к папке
                            archive_path = f"{format_name}/{new_filename}"
                            zip_file.writestr(archive_path, jpg_bytes.getvalue())
                            logger.debug(f"Added {archive_path} to zip")
                        else:
                            # Если конвертация не удалась, пробуем добавить оригинальный файл
                            logger.warning(f"Failed to convert {photo.original_filename}, adding original")
                            archive_path = f"{format_name}/{photo.original_filename}"
                            zip_file.write(photo_path, archive_path)
                            
                    except Exception as e:
                        logger.error(f"Error processing photo {photo.original_filename}: {e}")
                        try:
                            archive_path = f"{format_name}/{photo.original_filename}"
                            zip_file.write(photo_path, archive_path)
                        except:
                            logger.error(f"Failed to add original file {photo.original_filename}")
                else:
                    logger.warning(f"Photo file not found: {photo_path}")
    
    zip_buffer.seek(0)
    return zip_buffer

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Создание базы данных и администратора
with app.app_context():
    db.create_all()
    
    # Создание администратора по умолчанию
    if not User.query.filter_by(phone='admin').first():
        admin = User(
            phone='admin',
            full_name='Administrator',
            is_admin=True,
            sms_consent=True,
            privacy_consent=True
        )
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
    
    # Создание начального контента
    default_content = {
        'important_info': '✅ Минимальный заказ: 10 рублей\n✅ Бумага: только глянцевая 230 г/м²\n✅ Скидка: от 200 штук -5% на все форматы\n✅ Любой другой формат до 10x15 — 0.40 BYN\n✅ Любой формат до 7x10 — 0.25 BYN',
        'privacy_policy': '''<h6>1. Общие положения</h6>
<p>Настоящая политика обработки персональных данных составлена в соответствии с требованиями Закона Республики Беларусь от 7 мая 2021 г. № 99-З «О защите персональных данных»...</p>''',
        'format_examples': 'Примеры форматов будут загружены...'
    }
    
    for key, value in default_content.items():
        if not SiteContent.query.filter_by(key=key).first():
            content = SiteContent(key=key, value=value)
            db.session.add(content)
    
    db.session.commit()

# Маршруты для публичной части
@app.route('/')
def index():
    try:
        reviews = Review.query.filter_by(is_approved=True).order_by(Review.created_at.desc()).limit(5).all()
        active_lottery = Lottery.query.filter_by(is_active=True).filter(
            Lottery.end_date > datetime.now()
        ).first()
        
        # Получаем контент из базы данных
        important_info_obj = SiteContent.query.filter_by(key='important_info').first()
        privacy_policy_obj = SiteContent.query.filter_by(key='privacy_policy').first()
        format_examples_obj = SiteContent.query.filter_by(key='format_examples').first()
        
        # Преобразуем в значения или пустые строки
        important_info = important_info_obj.value if important_info_obj else ''
        privacy_policy = privacy_policy_obj.value if privacy_policy_obj else ''
        format_examples = format_examples_obj.value if format_examples_obj else ''
        
        print(f"Debug - important_info: {important_info[:50]}...")  # для отладки
        
        return render_template('index.html', 
                             reviews=reviews, 
                             active_lottery=active_lottery,
                             important_info=important_info,
                             privacy_policy=privacy_policy,
                             format_examples=format_examples)
    except Exception as e:
        print(f"Error in index route: {e}")
        # Возвращаем шаблон с пустыми значениями в случае ошибки
        return render_template('index.html', 
                             reviews=[], 
                             active_lottery=None,
                             important_info='',
                             privacy_policy='',
                             format_examples='')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        phone = request.form.get('phone')
        password = request.form.get('password')
        full_name = request.form.get('full_name')
        sms_consent = request.form.get('sms_consent') == 'on'
        privacy_consent = request.form.get('privacy_consent') == 'on'
        
        if not privacy_consent:
            flash('Необходимо согласие с политикой конфиденциальности', 'danger')
            return redirect(url_for('register'))
        
        if User.query.filter_by(phone=phone).first():
            flash('Пользователь с таким номером уже существует', 'danger')
            return redirect(url_for('register'))
        
        user = User(
            phone=phone,
            full_name=full_name,
            sms_consent=sms_consent,
            privacy_consent=privacy_consent
        )
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        login_user(user)
        flash('Регистрация успешна!', 'success')
        return redirect(url_for('index'))
    
    privacy_policy = SiteContent.query.filter_by(key='privacy_policy').first()
    return render_template('register.html', privacy_policy=privacy_policy.value if privacy_policy else '')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        phone = request.form.get('phone')
        password = request.form.get('password')
        
        user = User.query.filter_by(phone=phone).first()
        
        if user and user.check_password(password):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        
        flash('Неверный номер телефона или пароль', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/profile')
@login_required
def profile():
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
    return render_template('profile.html', orders=orders)

@app.route('/order/<int:order_id>')
@login_required
def view_order(order_id):
    order = Order.query.get_or_404(order_id)
    
    # Проверка доступа
    if order.user_id != current_user.id and not current_user.is_admin:
        abort(403)
    
    # Проверка возможности редактирования
    can_edit = order.can_edit_until and order.can_edit_until > datetime.now() and order.status == 'pending'
    
    return render_template('order_detail.html', order=order, can_edit=can_edit)

@app.route('/order/<int:order_id>/cancel', methods=['POST'])
@login_required
def cancel_order(order_id):
    order = Order.query.get_or_404(order_id)
    
    if order.user_id != current_user.id:
        abort(403)
    
    if order.can_edit_until and order.can_edit_until > datetime.now() and order.status == 'pending':
        order.status = 'cancelled'
        db.session.commit()
        flash('Заказ отменен', 'success')
    else:
        flash('Заказ больше нельзя отменить', 'danger')
    
    return redirect(url_for('view_order', order_id=order.id))

@app.route('/create_order', methods=['POST'])
@login_required
def create_order():
    # Создание заказа
    order = Order()
    order.order_number = order.generate_order_number()
    order.user_id = current_user.id
    order.recipient_name = request.form.get('recipient_name')
    order.phone = request.form.get('phone')
    order.delivery_method = request.form.get('delivery_method')
    order.notes = request.form.get('notes')
    order.can_edit_until = datetime.now() + timedelta(minutes=30)
    
    # Детали доставки
    delivery_details = {}
    if order.delivery_method == 'belpost':
        delivery_details['index'] = request.form.get('postal_index')
        delivery_details['address'] = request.form.get('address')
        delivery_details['apartment'] = request.form.get('apartment')
    else:  # europost
        delivery_details['office_number'] = request.form.get('office_number')
        delivery_details['city'] = request.form.get('city')
        delivery_details['address'] = request.form.get('delivery_address')
    
    order.delivery_details = json.dumps(delivery_details)
    
    # Обработка позиций заказа
    formats = request.form.getlist('format[]')
    quantities = request.form.getlist('quantity[]')
    
    total = 0
    for idx, (fmt, qty) in enumerate(zip(formats, quantities)):
        if not fmt or not qty:
            continue
        
        qty = int(qty)
        price = 0
        
        # Определение цены по формату
        if fmt == '10x15':
            price = 0.35
        elif fmt in ['10x10', '9x13']:
            price = 0.40
        elif fmt in ['polaroid-10x12', 'fuji-7x10', '5x15', 'minipolaroid-7x10']:
            price = 0.25
        elif 'до 10x15' in fmt.lower():
            price = 0.40
        else:
            price = 0.25
        
        subtotal = price * qty
        total += subtotal
        
        item = OrderItem(
            format_name=fmt,
            format_size=fmt,
            price_per_item=price,
            quantity=qty,
            subtotal=subtotal
        )
        order.items.append(item)
    
    # Применение скидки за количество
    total_photos = sum(item.quantity for item in order.items)
    if total_photos >= 200:
        total *= 0.95  # 5% скидка
    
    order.total_amount = total
    
    db.session.add(order)
    db.session.commit()
    
    # Обработка загруженных фотографий из временного хранилища
    session_id = session.get('temp_session_id')
    if session_id:
        temp_uploads = TempUpload.query.filter_by(session_id=session_id).all()
        
        for temp_upload in temp_uploads:
            # Перемещаем файл из временной папки в постоянную
            old_path = os.path.join(app.config['UPLOAD_FOLDER'], temp_upload.saved_filename)
            
            # Проверяем, что файл существует
            if os.path.exists(old_path):
                photo = OrderPhoto(
                    order_id=order.id,
                    original_filename=temp_upload.original_filename,
                    saved_filename=temp_upload.saved_filename,
                    file_size=temp_upload.file_size,
                    format=str(temp_upload.format_index),
                    file_path=old_path
                )
                db.session.add(photo)
            
            # Удаляем запись из временных
            db.session.delete(temp_upload)
        
        db.session.commit()
        
        # Очищаем сессию
        session.pop('temp_session_id', None)
    
    flash(f'Заказ #{order.order_number} успешно создан! Вы можете редактировать его в течение 30 минут.', 'success')
    return redirect(url_for('order_success', order_id=order.id))

@app.route('/order_success/<int:order_id>')
@login_required
def order_success(order_id):
    order = Order.query.get_or_404(order_id)
    if order.user_id != current_user.id and not current_user.is_admin:
        abort(403)
    
    return render_template('order_success.html', order=order)

@app.route('/track_order/<order_number>')
def track_order(order_number):
    order = Order.query.filter_by(order_number=order_number).first_or_404()
    
    tracking_urls = {
        'belpost': f'https://www.belpost.by/by/Otsleditotpravleniye?number={order.tracking_number}' if order.tracking_number else None,
        'europost': f'https://evropochta.by/tracking/{order.tracking_number}' if order.tracking_number else None
    }
    
    return render_template('track_order.html', order=order, tracking_urls=tracking_urls)

@app.route('/upload_photos', methods=['POST'])
@login_required
def upload_photos():
    """Загрузка фотографий через AJAX с сохранением во временную папку"""
    if 'photos' not in request.files:
        return jsonify({'error': 'No files uploaded'}), 400
    
    files = request.files.getlist('photos')
    format_index = request.form.get('format', '0')
    
    # Получаем или создаем session_id для временных файлов
    session_id = session.get('temp_session_id')
    if not session_id:
        session_id = uuid.uuid4().hex
        session['temp_session_id'] = session_id
    
    # Проверяем количество уже загруженных файлов
    existing_count = TempUpload.query.filter_by(session_id=session_id).count()
    if existing_count + len(files) > 100:  # Максимум 100 файлов
        return jsonify({'error': 'Максимум 100 файлов за заказ'}), 400
    
    saved_files = []
    errors = []
    
    for file in files:
        if file and file.filename:
            try:
                original_filename = file.filename
                original_ext = original_filename.rsplit('.', 1)[1].lower() if '.' in original_filename else ''
                
                # Генерируем уникальное имя
                unique_id = uuid.uuid4().hex
                temp_filename = f"temp_{unique_id}.{original_ext}"
                temp_path = os.path.join(app.config['TEMP_FOLDER'], temp_filename)
                
                # Сохраняем временный файл
                file.save(temp_path)
                
                if not os.path.exists(temp_path) or os.path.getsize(temp_path) == 0:
                    errors.append(f'Ошибка сохранения файла {original_filename}')
                    continue
                
                # Конвертируем в JPG
                final_filename = f"{unique_id}.jpg"
                final_path = os.path.join(app.config['UPLOAD_FOLDER'], final_filename)
                
                if convert_to_jpg(temp_path, final_path):
                    # Удаляем временный файл
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                    
                    if os.path.exists(final_path) and os.path.getsize(final_path) > 0:
                        # Сохраняем в базу данных временных загрузок
                        temp_upload = TempUpload(
                            session_id=session_id,
                            original_filename=original_filename,
                            saved_filename=final_filename,
                            file_size=os.path.getsize(final_path),
                            file_format=format_index,
                            format_index=int(format_index)
                        )
                        db.session.add(temp_upload)
                        db.session.commit()
                        
                        saved_files.append({
                            'original_filename': original_filename,
                            'saved_filename': final_filename,
                            'size': os.path.getsize(final_path),
                            'format': format_index
                        })
                    else:
                        errors.append(f'Ошибка конвертации файла {original_filename}')
                else:
                    errors.append(f'Ошибка конвертации файла {original_filename}')
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                        
            except Exception as e:
                logger.error(f"Error processing file {file.filename}: {str(e)}")
                errors.append(f'Ошибка обработки файла {file.filename}')
    
    # Получаем общее количество файлов для этого формата
    total_count = TempUpload.query.filter_by(session_id=session_id, format_index=int(format_index)).count()
    
    return jsonify({
        'success': len(saved_files) > 0,
        'files': saved_files,
        'total': total_count,
        'errors': errors
    })

@app.route('/delete_upload/<filename>', methods=['POST'])
@login_required
def delete_upload(filename):
    """Удаление загруженного файла"""
    session_id = session.get('temp_session_id')
    if not session_id:
        return jsonify({'error': 'Session not found'}), 404
    
    temp_upload = TempUpload.query.filter_by(
        session_id=session_id, 
        saved_filename=filename
    ).first()
    
    if temp_upload:
        # Удаляем файл
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if os.path.exists(filepath):
            os.remove(filepath)
        
        db.session.delete(temp_upload)
        db.session.commit()
        
        # Получаем обновленное количество
        remaining = TempUpload.query.filter_by(session_id=session_id).count()
        
        return jsonify({'success': True, 'total': remaining})
    
    return jsonify({'error': 'File not found'}), 404

@app.route('/add_review', methods=['POST'])
@login_required
def add_review():
    rating = request.form.get('rating')
    text = request.form.get('text')
    
    if not rating or not text:
        flash('Заполните все поля', 'danger')
        return redirect(url_for('index'))
    
    review = Review(
        user_id=current_user.id,
        user_name=current_user.full_name or current_user.phone,
        rating=int(rating),
        text=text,
        is_approved=False  # Требуется модерация
    )
    
    db.session.add(review)
    db.session.commit()
    
    flash('Спасибо за отзыв! Он появится после проверки.', 'success')
    return redirect(url_for('index'))

@app.route('/lottery/participate/<int:lottery_id>', methods=['POST'])
@login_required
def participate_lottery(lottery_id):
    lottery = Lottery.query.get_or_404(lottery_id)
    
    if not lottery.is_active or lottery.end_date < datetime.now():
        flash('Розыгрыш уже закончен', 'danger')
        return redirect(url_for('index'))
    
    # Проверка на повторное участие
    existing = LotteryParticipant.query.filter_by(
        lottery_id=lottery_id,
        user_id=current_user.id
    ).first()
    
    if existing:
        flash('Вы уже участвуете в этом розыгрыше', 'warning')
        return redirect(url_for('index'))
    
    participant = LotteryParticipant(
        lottery_id=lottery_id,
        user_id=current_user.id,
        phone=current_user.phone
    )
    
    db.session.add(participant)
    db.session.commit()
    
    flash('Вы участвуете в розыгрыше! Удачи!', 'success')
    return redirect(url_for('index'))

# Админские маршруты
@app.route('/admin')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        abort(403)
    
    total_orders = Order.query.count()
    pending_orders = Order.query.filter_by(status='pending').count()
    total_users = User.query.count()
    recent_orders = Order.query.order_by(Order.created_at.desc()).limit(5).all()
    
    # Получаем контент для редактирования
    important_info = SiteContent.query.filter_by(key='important_info').first()
    privacy_policy = SiteContent.query.filter_by(key='privacy_policy').first()
    
    return render_template('admin/dashboard.html',
                         total_orders=total_orders,
                         pending_orders=pending_orders,
                         total_users=total_users,
                         recent_orders=recent_orders,
                         important_info=important_info.value if important_info else '',
                         privacy_policy=privacy_policy.value if privacy_policy else '')

@app.route('/admin/orders')
@login_required
def admin_orders():
    if not current_user.is_admin:
        abort(403)
    
    status = request.args.get('status', 'all')
    
    if status == 'all':
        orders = Order.query.order_by(Order.created_at.desc()).all()
    else:
        orders = Order.query.filter_by(status=status).order_by(Order.created_at.desc()).all()
    
    return render_template('admin/orders.html', orders=orders, current_status=status)

@app.route('/admin/order/<int:order_id>', methods=['GET', 'POST'])
@login_required
def admin_order_detail(order_id):
    if not current_user.is_admin:
        abort(403)
    
    order = Order.query.get_or_404(order_id)
    
    if request.method == 'POST':
        order.status = request.form.get('status')
        tracking_number = request.form.get('tracking_number')
        
        if tracking_number:
            order.tracking_number = tracking_number
        
        db.session.commit()
        flash('Заказ обновлен', 'success')
        return redirect(url_for('admin_order_detail', order_id=order.id))
    
    return render_template('admin/order_detail.html', order=order)

@app.route('/admin/order/<int:order_id>/download_photos')
@login_required
def download_order_photos(order_id):
    if not current_user.is_admin:
        abort(403)
    
    zip_buffer = create_zip_from_photos(order_id)
    order = Order.query.get_or_404(order_id)
    
    return send_file(
        zip_buffer,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f'order_{order.order_number}_photos.zip'
    )

@app.route('/admin/reviews')
@login_required
def admin_reviews():
    if not current_user.is_admin:
        abort(403)
    
    reviews = Review.query.order_by(Review.created_at.desc()).all()
    return render_template('admin/reviews.html', reviews=reviews)

@app.route('/admin/lotteries')
@login_required
def admin_lotteries():
    if not current_user.is_admin:
        abort(403)
    
    lotteries = Lottery.query.order_by(Lottery.start_date.desc()).all()
    return render_template('admin/lotteries.html', lotteries=lotteries, now=datetime.now)

@app.route('/admin/review/<int:review_id>/approve', methods=['POST'])
@login_required
def approve_review(review_id):
    if not current_user.is_admin:
        abort(403)
    
    review = Review.query.get_or_404(review_id)
    review.is_approved = True
    db.session.commit()
    
    flash('Отзыв одобрен', 'success')
    return redirect(url_for('admin_reviews'))

@app.route('/admin/review/<int:review_id>/delete', methods=['POST'])
@login_required
def delete_review(review_id):
    if not current_user.is_admin:
        abort(403)
    
    review = Review.query.get_or_404(review_id)
    db.session.delete(review)
    db.session.commit()
    
    flash('Отзыв удален', 'success')
    return redirect(url_for('admin_reviews'))


@app.route('/admin/lottery/create', methods=['POST'])
@login_required
def create_lottery():
    if not current_user.is_admin:
        abort(403)
    
    title = request.form.get('title')
    description = request.form.get('description')
    prize = request.form.get('prize')
    end_date_str = request.form.get('end_date')
    
    if not all([title, description, prize, end_date_str]):
        flash('Заполните все поля', 'danger')
        return redirect(url_for('admin_lotteries'))
    
    try:
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        # Устанавливаем время окончания на конец дня
        end_date = end_date.replace(hour=23, minute=59, second=59)
    except ValueError:
        flash('Неверный формат даты', 'danger')
        return redirect(url_for('admin_lotteries'))
    
    lottery = Lottery(
        title=title,
        description=description,
        prize=prize,
        start_date=datetime.now(),
        end_date=end_date,
        is_active=True
    )
    
    db.session.add(lottery)
    db.session.commit()
    
    flash('Розыгрыш создан', 'success')
    return redirect(url_for('admin_lotteries'))

@app.route('/admin/site_content/<key>', methods=['POST'])
@login_required
def update_site_content(key):
    if not current_user.is_admin:
        abort(403)
    
    content = SiteContent.query.filter_by(key=key).first_or_404()
    content.value = request.form.get('value')
    db.session.commit()
    
    flash('Контент обновлен', 'success')
    return redirect(request.referrer or url_for('admin_dashboard'))

if __name__ == '__main__':
    app.run(debug=True)