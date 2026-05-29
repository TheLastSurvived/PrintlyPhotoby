from config import db, app
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import uuid

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
    delivery_method = db.Column(db.String(20), nullable=False)
    delivery_details = db.Column(db.Text, nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')
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
    format = db.Column(db.String(50))
    file_path = db.Column(db.String(500))

class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    user_name = db.Column(db.String(100))
    rating = db.Column(db.Integer, nullable=False)
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

class Price(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    format_key = db.Column(db.String(50), unique=True, nullable=False)
    format_name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    min_quantity = db.Column(db.Integer, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    sort_order = db.Column(db.Integer, default=0)

class FormatExample(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(200))
    image_url = db.Column(db.String(500))
    sort_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)

class Contact(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    title = db.Column(db.String(100), nullable=False)
    icon = db.Column(db.String(200), nullable=False)
    value = db.Column(db.String(200), nullable=False)
    sort_order = db.Column(db.Integer, default=0)


class Video(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    filename = db.Column(db.String(200), nullable=False)
    description = db.Column(db.String(500))
    sort_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now)