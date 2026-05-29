from config import app, db, logger
from models import User, Order, OrderPhoto, Review, Lottery, SiteContent, Price, FormatExample, TempUpload, SiteContent
from utils import create_zip_from_photos
from datetime import datetime
import uuid
import os
from flask import render_template, request, redirect, url_for, flash, jsonify, send_file, abort
from flask_login import login_required, current_user, login_user
from werkzeug.utils import secure_filename

# ========== АДМИНСКИЕ МАРШРУТЫ ==========

@app.route('/admin')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        abort(403)
    
    total_orders = Order.query.count()
    pending_orders = Order.query.filter_by(status='pending').count()
    total_users = User.query.count()
    recent_orders = Order.query.order_by(Order.created_at.desc()).limit(5).all()
    
    important_info = SiteContent.query.filter_by(key='important_info').first()
    privacy_policy = SiteContent.query.filter_by(key='privacy_policy').first()
    
    # Получаем hero-контент
    hero_title = SiteContent.query.filter_by(key='hero_title').first()
    hero_subtitle = SiteContent.query.filter_by(key='hero_subtitle').first()
    hero_button_text = SiteContent.query.filter_by(key='hero_button_text').first()
    
    return render_template('admin/dashboard.html',
                         total_orders=total_orders,
                         pending_orders=pending_orders,
                         total_users=total_users,
                         recent_orders=recent_orders,
                         important_info=important_info.value if important_info else '',
                         privacy_policy=privacy_policy.value if privacy_policy else '',
                         hero_title=hero_title.value if hero_title else 'Печать фотографий <br>с душой и вниманием к деталям',
                         hero_subtitle=hero_subtitle.value if hero_subtitle else 'Только печать на заказ. Отправка Белпочтой и Европочтой',
                         hero_button_text=hero_button_text.value if hero_button_text else 'Оформить заказ')

@app.route('/admin/orders')
@login_required
def admin_orders():
    if not current_user.is_admin:
        abort(403)
    
    status = request.args.get('status', 'all')
    search = request.args.get('search', '').strip()
    
    # Базовый запрос
    query = Order.query
    
    # Фильтр по статусу
    if status != 'all':
        query = query.filter_by(status=status)
    
    # Фильтр по поиску (ФИО, номер телефона, номер заказа)
    if search:
        query = query.filter(
            db.or_(
                Order.recipient_name.ilike(f'%{search}%'),
                Order.phone.ilike(f'%{search}%'),
                Order.order_number.ilike(f'%{search}%')
            )
        )
    
    orders = query.order_by(Order.created_at.desc()).all()
    
    return render_template('admin/orders.html', orders=orders, current_status=status, search=search)

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

@app.route('/admin/prices')
@login_required
def admin_prices():
    if not current_user.is_admin:
        abort(403)
    
    prices = Price.query.order_by(Price.sort_order).all()
    return render_template('admin/prices.html', prices=prices)

@app.route('/admin/price/update/<int:price_id>', methods=['POST'])
@login_required
def update_price(price_id):
    if not current_user.is_admin:
        abort(403)
    
    price_entry = Price.query.get_or_404(price_id)
    price_entry.price = float(request.form.get('price'))
    price_entry.min_quantity = int(request.form.get('min_quantity'))
    price_entry.is_active = request.form.get('is_active') == 'on'
    db.session.commit()
    
    flash('Цена обновлена', 'success')
    return redirect(url_for('admin_prices'))

@app.route('/admin/price/create', methods=['POST'])
@login_required
def create_price():
    if not current_user.is_admin:
        abort(403)
    
    price_entry = Price(
        format_key=request.form.get('format_key'),
        format_name=request.form.get('format_name'),
        price=float(request.form.get('price')),
        min_quantity=int(request.form.get('min_quantity')),
        sort_order=int(request.form.get('sort_order', 99)),
        is_active=True
    )
    db.session.add(price_entry)
    db.session.commit()
    
    flash('Новый формат добавлен', 'success')
    return redirect(url_for('admin_prices'))

@app.route('/admin/price/delete/<int:price_id>', methods=['POST'])
@login_required
def delete_price(price_id):
    if not current_user.is_admin:
        abort(403)
    
    price_entry = Price.query.get_or_404(price_id)
    db.session.delete(price_entry)
    db.session.commit()
    
    flash('Формат удален', 'success')
    return redirect(url_for('admin_prices'))

@app.route('/admin/format-examples')
@login_required
def admin_format_examples():
    if not current_user.is_admin:
        abort(403)
    
    examples = FormatExample.query.order_by(FormatExample.sort_order).all()
    return render_template('admin/format_examples.html', examples=examples)

@app.route('/admin/format-example/update/<int:example_id>', methods=['POST'])
@login_required
def update_format_example(example_id):
    if not current_user.is_admin:
        abort(403)
    
    example = FormatExample.query.get_or_404(example_id)
    example.title = request.form.get('title')
    example.description = request.form.get('description')
    example.is_active = request.form.get('is_active') == 'on'
    
    if 'image' in request.files:
        file = request.files['image']
        if file and file.filename:
            allowed_extensions = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
            ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
            
            if ext in allowed_extensions:
                unique_id = uuid.uuid4().hex[:8]
                filename = secure_filename(f"{example.id}_{unique_id}.{ext}")
                filepath = os.path.join(app.config['EXAMPLES_FOLDER'], filename)
                
                file.save(filepath)
                
                if example.image_url:
                    old_path = os.path.join('static', example.image_url.lstrip('/'))
                    if os.path.exists(old_path):
                        os.remove(old_path)
                
                example.image_url = f'/uploads/examples/{filename}'
    
    db.session.commit()
    flash('Пример формата обновлен', 'success')
    return redirect(url_for('admin_format_examples'))

@app.route('/admin/format-example/create', methods=['POST'])
@login_required
def create_format_example():
    if not current_user.is_admin:
        abort(403)
    
    title = request.form.get('title')
    description = request.form.get('description')
    sort_order = int(request.form.get('sort_order', 99))
    
    example = FormatExample(
        title=title,
        description=description,
        sort_order=sort_order,
        is_active=True,
        image_url=''
    )
    db.session.add(example)
    db.session.commit()
    
    if 'image' in request.files:
        file = request.files['image']
        if file and file.filename:
            allowed_extensions = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
            ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
            
            if ext in allowed_extensions:
                unique_id = uuid.uuid4().hex[:8]
                filename = secure_filename(f"{example.id}_{unique_id}.{ext}")
                filepath = os.path.join(app.config['EXAMPLES_FOLDER'], filename)
                
                file.save(filepath)
                
                example.image_url = f'/uploads/examples/{filename}'
                db.session.commit()
    
    flash('Пример формата добавлен', 'success')
    return redirect(url_for('admin_format_examples'))

@app.route('/admin/format-example/delete/<int:example_id>')
@login_required
def delete_format_example(example_id):
    if not current_user.is_admin:
        abort(403)
    
    example = FormatExample.query.get_or_404(example_id)
    
    if example.image_url:
        filepath = os.path.join('static', example.image_url.lstrip('/'))
        if os.path.exists(filepath):
            os.remove(filepath)
    
    db.session.delete(example)
    db.session.commit()
    
    flash('Пример удален', 'success')
    return redirect(url_for('admin_format_examples'))

@app.route('/admin/users')
@login_required
def admin_users():
    if not current_user.is_admin:
        abort(403)
    
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=users)

@app.route('/admin/reset_user_password/<int:user_id>', methods=['POST'])
@login_required
def admin_reset_user_password(user_id):
    if not current_user.is_admin:
        return jsonify({'success': False, 'error': 'Доступ запрещен'}), 403
    
    user = User.query.get_or_404(user_id)
    
    if request.is_json:
        data = request.get_json()
        new_password = data.get('password')
    else:
        new_password = request.form.get('new_password')
    
    if not new_password or len(new_password) < 6:
        return jsonify({'success': False, 'error': 'Пароль должен быть не менее 6 символов'})
    
    user.set_password(new_password)
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == 'admin':
            user = User.query.filter_by(phone=username).first()
            if user and user.check_password(password):
                login_user(user)
                return redirect(url_for('admin_dashboard'))
        
        flash('Неверный логин или пароль', 'danger')
    
    return render_template('admin/admin_login.html')

@app.route('/admin/order/<int:order_id>/delete_photo/<int:photo_id>', methods=['POST'])
@login_required
def admin_delete_photo(order_id, photo_id):
    if not current_user.is_admin:
        abort(403)
    
    order = Order.query.get_or_404(order_id)
    photo = OrderPhoto.query.get_or_404(photo_id)
    
    if photo.order_id != order.id:
        abort(404)
    
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], photo.saved_filename)
    if os.path.exists(filepath):
        os.remove(filepath)
        logger.info(f"Deleted photo file: {filepath}")
    
    db.session.delete(photo)
    db.session.commit()
    
    flash(f'Фото "{photo.original_filename}" удалено', 'success')
    return redirect(url_for('admin_order_detail', order_id=order.id))

@app.route('/admin/order/<int:order_id>/delete_all_photos', methods=['POST'])
@login_required
def admin_delete_all_photos(order_id):
    if not current_user.is_admin:
        abort(403)
    
    order = Order.query.get_or_404(order_id)
    deleted_count = 0
    
    for photo in order.photos:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], photo.saved_filename)
        if os.path.exists(filepath):
            os.remove(filepath)
        db.session.delete(photo)
        deleted_count += 1
    
    db.session.commit()
    flash(f'Удалено {deleted_count} фото из заказа #{order.order_number}', 'success')
    return redirect(url_for('admin_order_detail', order_id=order.id))

@app.route('/admin/cleanup_temp_files', methods=['POST'])
@login_required
def admin_cleanup_temp_files():
    if not current_user.is_admin:
        abort(403)
    
    deleted_count = 0
    deleted_size = 0
    
    temp_uploads = TempUpload.query.all()
    for temp in temp_uploads:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], temp.saved_filename)
        if os.path.exists(filepath):
            file_size = os.path.getsize(filepath)
            os.remove(filepath)
            deleted_size += file_size
            deleted_count += 1
        db.session.delete(temp)
    
    upload_folder = app.config['UPLOAD_FOLDER']
    if os.path.exists(upload_folder):
        for filename in os.listdir(upload_folder):
            if filename.startswith('temp_'):
                filepath = os.path.join(upload_folder, filename)
                exists_in_db = TempUpload.query.filter_by(saved_filename=filename).first()
                exists_in_order = OrderPhoto.query.filter_by(saved_filename=filename).first()
                
                if not exists_in_db and not exists_in_order:
                    if os.path.exists(filepath):
                        file_size = os.path.getsize(filepath)
                        os.remove(filepath)
                        deleted_size += file_size
                        deleted_count += 1
                        logger.info(f"Deleted orphaned file: {filename}")
    
    db.session.commit()
    
    size_mb = deleted_size / (1024 * 1024)
    flash(f'Очищено {deleted_count} файлов ({size_mb:.2f} МБ)', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/storage_stats')
@login_required
def admin_storage_stats():
    if not current_user.is_admin:
        abort(403)
    
    stats = {
        'total_photos': OrderPhoto.query.count(),
        'total_temp': TempUpload.query.count(),
        'total_orders': Order.query.count(),
        'photos_by_order': []
    }
    
    total_size = 0
    upload_folder = app.config['UPLOAD_FOLDER']
    
    if os.path.exists(upload_folder):
        for filename in os.listdir(upload_folder):
            filepath = os.path.join(upload_folder, filename)
            if os.path.isfile(filepath):
                total_size += os.path.getsize(filepath)
    
    stats['total_size_mb'] = round(total_size / (1024 * 1024), 2)
    
    orders = Order.query.order_by(Order.created_at.desc()).limit(20).all()
    for order in orders:
        stats['photos_by_order'].append({
            'id': order.id,
            'order_number': order.order_number,
            'photos_count': len(order.photos),
            'created_at': order.created_at
        })
    
    return render_template('admin/storage_stats.html', stats=stats)


from werkzeug.utils import secure_filename
import uuid
import os

@app.route('/admin/hero_content', methods=['GET', 'POST'])
@login_required
def admin_hero_content():
    if not current_user.is_admin:
        abort(403)
    
    hero_title = SiteContent.query.filter_by(key='hero_title').first()
    hero_subtitle = SiteContent.query.filter_by(key='hero_subtitle').first()
    hero_button_text = SiteContent.query.filter_by(key='hero_button_text').first()
    hero_background_image = SiteContent.query.filter_by(key='hero_background_image').first()
    
    if request.method == 'POST':
        # Обновляем текстовые поля
        for key, value in [
            ('hero_title', request.form.get('hero_title')),
            ('hero_subtitle', request.form.get('hero_subtitle')),
            ('hero_button_text', request.form.get('hero_button_text'))
        ]:
            content = SiteContent.query.filter_by(key=key).first()
            if content:
                content.value = value
            else:
                content = SiteContent(key=key, value=value)
                db.session.add(content)
        
        # Обработка загрузки изображения
        if 'hero_image' in request.files:
            file = request.files['hero_image']
            if file and file.filename:
                allowed_extensions = {'jpg', 'jpeg', 'png', 'gif', 'webp', 'svg'}
                ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
                
                if ext in allowed_extensions:
                    # Удаляем старое изображение (если не стандартное)
                    if hero_background_image and hero_background_image.value:
                        old_path = hero_background_image.value.replace('/static/', 'static/')
                        if os.path.exists(old_path) and 'fon.jpg' not in old_path:
                            os.remove(old_path)
                    
                    # Сохраняем новое изображение
                    unique_id = uuid.uuid4().hex[:8]
                    filename = secure_filename(f"hero_bg_{unique_id}.{ext}")
                    filepath = os.path.join('static', 'image', filename)
                    
                    # Создаем папку если нет
                    os.makedirs(os.path.dirname(filepath), exist_ok=True)
                    
                    file.save(filepath)
                    new_image_url = f'/static/image/{filename}'
                    
                    if hero_background_image:
                        hero_background_image.value = new_image_url
                    else:
                        hero_background_image = SiteContent(key='hero_background_image', value=new_image_url)
                        db.session.add(hero_background_image)
        
        # Сброс на стандартное изображение
        if request.form.get('reset_image') == 'on':
            default_image = '/static/image/fon.jpg'
            if hero_background_image:
                hero_background_image.value = default_image
            else:
                hero_background_image = SiteContent(key='hero_background_image', value=default_image)
                db.session.add(hero_background_image)
            
            # Удаляем загруженное изображение если есть
            if hero_background_image and hero_background_image.value != default_image:
                old_path = hero_background_image.value.replace('/static/', 'static/')
                if os.path.exists(old_path) and 'fon.jpg' not in old_path:
                    os.remove(old_path)
        
        db.session.commit()
        flash('Hero-блок обновлен', 'success')
        return redirect(url_for('admin_hero_content'))
    
    return render_template('admin/hero_content.html',
                         hero_title=hero_title.value if hero_title else '',
                         hero_subtitle=hero_subtitle.value if hero_subtitle else '',
                         hero_button_text=hero_button_text.value if hero_button_text else '',
                         hero_background_image=hero_background_image.value if hero_background_image else '/static/image/fon.jpg')