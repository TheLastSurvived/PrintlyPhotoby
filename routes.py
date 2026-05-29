from config import app, db, login_manager, logger
from models import User, Order, OrderItem, OrderPhoto, Review, Lottery, LotteryParticipant, SiteContent, TempUpload, Price, FormatExample, Contact
from utils import convert_to_jpg, convert_to_jpg_bytes, get_privacy_policy 
from datetime import datetime, timedelta
import json
import uuid
import os
from flask import render_template, request, redirect, url_for, flash, jsonify, abort, session
from flask_login import login_user, logout_user, login_required, current_user

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Создание базы данных и начальных данных
with app.app_context():
    db.create_all()
    
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
    
    default_prices = [
        ('10x15', '10 x 15 см', 0.35, 26, 1),
        ('10x10', '10 x 10 см', 0.40, 50, 2),
        ('9x13', '9 x 13 см', 0.40, 26, 3),
        ('polaroid-10x12', 'Polaroid 10 x 12 см', 0.25, 40, 4),
        ('fuji-7x10', 'Fuji / Instax 7 x 10 см', 0.25, 40, 5),
        ('minipolaroid-7x10', 'MiniPolaroid 7 x 10 см', 0.25, 50, 6),
        ('5x15', 'Фотополоска 5 x 15 см', 0.25, 40, 7),
        ('other-up-to-10x15', 'Другой формат (до 10x15)', 0.40, 0, 8),
        ('other-up-to-7x10', 'Другой формат (до 7x10)', 0.25, 0, 9),
    ]
    
    for format_key, format_name, price, min_qty, sort_order in default_prices:
        if not Price.query.filter_by(format_key=format_key).first():
            price_entry = Price(
                format_key=format_key,
                format_name=format_name,
                price=price,
                min_quantity=min_qty,
                sort_order=sort_order,
                is_active=True
            )
            db.session.add(price_entry)
    
    default_examples = [
        ('10x15', 'Классический формат для семейных фото', '/static/images/example-10x15.jpg', 1),
        ('10x10', 'Квадратный формат, отлично подходит для Instagram', '/static/images/example-10x10.jpg', 2),
        ('Polaroid', 'Стильный формат с эффектом полароид', '/static/images/example-polaroid.jpg', 3),
        ('Instax', 'Компактный формат как мгновенные фото', '/static/images/example-instax.jpg', 4),
    ]
    
    for title, desc, img_url, sort_order in default_examples:
        if not FormatExample.query.filter_by(title=title).first():
            example = FormatExample(
                title=title,
                description=desc,
                image_url=img_url,
                sort_order=sort_order,
                is_active=True
            )
            db.session.add(example)
    
    default_content = {
        'important_info': '✅ Минимальный заказ: 10 рублей\n✅ Бумага: только глянцевая 230 г/м²\n✅ Скидка: от 200 штук -5% на все форматы',
        'hero_title': 'Печать фотографий <br>с душой и вниманием к деталям',
        'hero_subtitle': 'Только печать на заказ. Отправка Белпочтой и Европочтой',
        'hero_button_text': 'Оформить заказ',
        'hero_background_image': '/static/image/fon.jpg',
        'footer_unp': 'УНП 123456789',
        'footer_schedule': 'Пн-Пт: 9:00 - 18:00<br>Сб-Вс: выходной',
    }
    
    for key, value in default_content.items():
        if not SiteContent.query.filter_by(key=key).first():
            content = SiteContent(key=key, value=value)
            db.session.add(content)
    
    db.session.commit()


@app.context_processor
def inject_footer_data():
    """Передает данные для футера во все шаблоны"""
    from utils import get_privacy_policy
    
    footer_unp_obj = SiteContent.query.filter_by(key='footer_unp').first()
    footer_schedule_obj = SiteContent.query.filter_by(key='footer_schedule').first()
    
    return {
        'footer_unp': footer_unp_obj.value if footer_unp_obj else 'УНП 123456789',
        'footer_schedule': footer_schedule_obj.value if footer_schedule_obj else 'Пн-Пт: 9:00 - 18:00<br>Сб-Вс: выходной',
        'privacy_policy': get_privacy_policy()
    }

# ========== ПУБЛИЧНЫЕ МАРШРУТЫ ==========

@app.route('/')
def index():
    try:
        contacts = Contact.query.order_by(Contact.sort_order).all()
        reviews = Review.query.filter_by(is_approved=True).order_by(Review.created_at.desc()).limit(5).all()
        active_lottery = Lottery.query.filter_by(is_active=True).filter(
            Lottery.end_date > datetime.now()
        ).first()
        
        important_info_obj = SiteContent.query.filter_by(key='important_info').first()

        hero_title_obj = SiteContent.query.filter_by(key='hero_title').first()
        hero_subtitle_obj = SiteContent.query.filter_by(key='hero_subtitle').first()
        hero_button_text_obj = SiteContent.query.filter_by(key='hero_button_text').first()

        hero_background_image_obj = SiteContent.query.filter_by(key='hero_background_image').first()
        hero_background_image = hero_background_image_obj.value if hero_background_image_obj else '/static/image/fon.jpg'
        
        prices = Price.query.filter_by(is_active=True).order_by(Price.sort_order).all()
        format_examples = FormatExample.query.filter_by(is_active=True).order_by(FormatExample.sort_order).all()
        
        important_info = important_info_obj.value if important_info_obj else ''

        hero_title = hero_title_obj.value if hero_title_obj else 'Печать фотографий <br>с душой и вниманием к деталям'
        hero_subtitle = hero_subtitle_obj.value if hero_subtitle_obj else 'Только печать на заказ. Отправка Белпочтой и Европочтой'
        hero_button_text = hero_button_text_obj.value if hero_button_text_obj else 'Оформить заказ'

        
        
        return render_template('index.html', 
                             reviews=reviews, 
                             active_lottery=active_lottery,
                             important_info=important_info,
                             prices=prices,
                             contacts=contacts,
                             format_examples=format_examples,
                             hero_title=hero_title,
                             hero_subtitle=hero_subtitle,
                             hero_button_text=hero_button_text,
                             hero_background_image=hero_background_image)
    except Exception as e:
        print(f"Error in index route: {e}")
        return render_template('index.html', 
                             reviews=[], 
                             active_lottery=None,
                             important_info='',
                             prices=[],
                             contacts=[],
                             format_examples=[],
                             hero_title=hero_title,
                             hero_subtitle=hero_subtitle,
                             hero_button_text=hero_button_text)

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
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        phone = request.form.get('phone')
        password = request.form.get('password')
        
        phone = ''.join(c for c in phone if c.isdigit())
        
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
    
    if order.user_id != current_user.id and not current_user.is_admin:
        abort(403)
    
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
    order = Order()
    order.order_number = order.generate_order_number()
    order.user_id = current_user.id
    order.recipient_name = request.form.get('recipient_name')
    order.phone = request.form.get('phone')
    order.delivery_method = request.form.get('delivery_method')
    order.notes = request.form.get('notes')
    order.can_edit_until = datetime.now() + timedelta(minutes=30)
    
    delivery_details = {}
    if order.delivery_method == 'belpost':
        delivery_details['index'] = request.form.get('postal_index')
        delivery_details['address'] = request.form.get('address')
        delivery_details['apartment'] = request.form.get('apartment')
    else:
        delivery_details['office_number'] = request.form.get('office_number')
        delivery_details['city'] = request.form.get('city')
        delivery_details['address'] = request.form.get('delivery_address')
    
    order.delivery_details = json.dumps(delivery_details)
    
    formats = request.form.getlist('format[]')
    quantities = request.form.getlist('quantity[]')
    
    prices_map = {}
    for price_entry in Price.query.filter_by(is_active=True).all():
        prices_map[price_entry.format_key] = {
            'price': price_entry.price,
            'min_qty': price_entry.min_quantity
        }
    
    total = 0
    for idx, (fmt, qty) in enumerate(zip(formats, quantities)):
        if not fmt or not qty:
            continue
        
        qty = int(qty)
        price_data = prices_map.get(fmt, {'price': 0.35, 'min_qty': 0})
        price = price_data['price']
        
        min_qty = price_data['min_qty']
        if min_qty > 0 and qty < min_qty:
            flash(f'Внимание: Для формата {fmt} рекомендуемое минимальное количество - {min_qty} шт', 'warning')
        
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
    
    total_photos = sum(item.quantity for item in order.items)
    if total_photos >= 200:
        total *= 0.95
    
    order.total_amount = total
    if total < 10:
        flash('Минимальная сумма заказа - 10 BYN', 'danger')
        return redirect(url_for('index'))
    
    db.session.add(order)
    db.session.commit()
    
    session_id = session.get('temp_session_id')
    if session_id:
        temp_uploads = TempUpload.query.filter_by(session_id=session_id).all()
        
        for temp_upload in temp_uploads:
            old_path = os.path.join(app.config['UPLOAD_FOLDER'], temp_upload.saved_filename)
            
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
            
            db.session.delete(temp_upload)
        
        db.session.commit()
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
        'europost': f'https://evropochta.by' if order.tracking_number else None
    }
    
    return render_template('track_order.html', order=order, tracking_urls=tracking_urls)

@app.route('/upload_photos', methods=['POST'])
@login_required
def upload_photos():
    if 'photos' not in request.files:
        return jsonify({'error': 'No files uploaded'}), 400
    
    files = request.files.getlist('photos')
    format_index = request.form.get('format', '0')
    
    session_id = session.get('temp_session_id')
    if not session_id:
        session_id = uuid.uuid4().hex
        session['temp_session_id'] = session_id
    
    existing_count = TempUpload.query.filter_by(session_id=session_id).count()
    if existing_count + len(files) > 100:
        return jsonify({'error': 'Максимум 100 файлов за заказ'}), 400
    
    saved_files = []
    errors = []
    
    for file in files:
        if file and file.filename:
            try:
                original_filename = file.filename
                original_ext = original_filename.rsplit('.', 1)[1].lower() if '.' in original_filename else ''
                
                unique_id = uuid.uuid4().hex
                temp_filename = f"temp_{unique_id}.{original_ext}"
                temp_path = os.path.join(app.config['TEMP_FOLDER'], temp_filename)
                
                file.save(temp_path)
                
                if not os.path.exists(temp_path) or os.path.getsize(temp_path) == 0:
                    errors.append(f'Ошибка сохранения файла {original_filename}')
                    continue
                
                final_filename = f"{unique_id}.jpg"
                final_path = os.path.join(app.config['UPLOAD_FOLDER'], final_filename)
                
                if convert_to_jpg(temp_path, final_path):
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                    
                    if os.path.exists(final_path) and os.path.getsize(final_path) > 0:
                        existing = TempUpload.query.filter_by(
                            session_id=session_id, 
                            saved_filename=final_filename
                        ).first()
                        
                        if not existing:
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
    
    return jsonify({
        'success': len(saved_files) > 0,
        'files': saved_files,
        'total': len(saved_files),
        'errors': errors
    })

@app.route('/delete_upload/<filename>', methods=['POST'])
@login_required
def delete_upload(filename):
    session_id = session.get('temp_session_id')
    if not session_id:
        return jsonify({'error': 'Session not found'}), 404
    
    temp_upload = TempUpload.query.filter_by(
        session_id=session_id, 
        saved_filename=filename
    ).first()
    
    if temp_upload:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if os.path.exists(filepath):
            os.remove(filepath)
        
        db.session.delete(temp_upload)
        db.session.commit()
        
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
        is_approved=False
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

@app.route('/update_contacts', methods=['POST'])
@login_required
def update_contacts():
    if not current_user.is_admin:
        abort(403)
    
    contacts_data = {
        'address': {'title': 'Адрес', 'icon': '📍'},
        'phone': {'title': 'Телефон', 'icon': '<i class="bi bi-telephone-fill"></i>'},
        'telegram': {'title': 'Telegram', 'icon': '<i class="bi bi-telegram"></i>'},
        'viber': {'title': 'Viber', 'icon': '<i class="bi bi-chat-dots-fill"></i>'}
    }
    
    for key, data in contacts_data.items():
        contact = Contact.query.filter_by(key=key).first()
        value = request.form.get(key, '')
        if contact:
            contact.value = value
        else:
            contact = Contact(key=key, title=data['title'], icon=data['icon'], value=value)
            db.session.add(contact)
    
    db.session.commit()
    flash('Контакты обновлены', 'success')
    return redirect(url_for('index'))


@app.route('/sitemap.xml')
def sitemap():
    """Генерирует sitemap.xml для поисковых систем"""
    from config import app
    
    # Базовый URL сайта (замени на свой домен)
    base_url = 'https://printly.by'  # <-- ЗАМЕНИ НА СВОЙ ДОМЕН
    
    # Страницы для индексации
    pages = [
        {'loc': '/', 'priority': '1.0', 'changefreq': 'daily'},
        {'loc': '/#services', 'priority': '0.8', 'changefreq': 'weekly'},
        {'loc': '/#price', 'priority': '0.8', 'changefreq': 'weekly'},
        {'loc': '/#order', 'priority': '0.7', 'changefreq': 'weekly'},
        {'loc': '/#contacts', 'priority': '0.6', 'changefreq': 'monthly'},
        {'loc': '/#reviews', 'priority': '0.6', 'changefreq': 'weekly'},
    ]
    
    # Генерируем XML
    sitemap_xml = render_template('sitemap.xml', pages=pages, base_url=base_url)
    return app.response_class(sitemap_xml, mimetype='application/xml')


@app.context_processor
def utility_processor():
    """Добавляет функции во все шаблоны"""
    def now():
        return datetime.now().strftime('%Y-%m-%d')
    return dict(now=now)