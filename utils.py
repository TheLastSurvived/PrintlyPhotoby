import os
import zipfile
from io import BytesIO
from PIL import Image
import pillow_heif
from config import app, logger
from models import Order, Price, OrderPhoto
from werkzeug.utils import secure_filename

def allowed_file(filename):
    allowed = app.config['ALLOWED_EXTENSIONS']
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed

def convert_to_jpg(image_path, output_path, quality=95):
    """Конвертирует изображение в JPG с сохранением качества"""
    try:
        file_ext = os.path.splitext(image_path)[1].lower()
        
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
        
        if img.mode in ('RGBA', 'LA', 'P'):
            rgb_img = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'RGBA':
                rgb_img.paste(img, mask=img.split()[-1])
            else:
                rgb_img.paste(img)
            img = rgb_img
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        
        img.save(output_path, 'JPEG', quality=quality, optimize=True)
        return True
    except Exception as e:
        print(f"Error converting image {image_path}: {e}")
        return False

def convert_to_jpg_bytes(image_path, quality=95):
    """Конвертирует изображение в JPG и возвращает BytesIO объект"""
    try:
        logger.debug(f"Converting to bytes: {image_path}")
        
        file_ext = os.path.splitext(image_path)[1].lower()
        img = None
        
        if file_ext in ['.heic', '.heif']:
            try:
                logger.debug(f"Processing HEIC/HEIF file for zip: {image_path}")
                heif_file = pillow_heif.open_heif(image_path)
                
                img = Image.frombytes(
                    heif_file.mode,
                    heif_file.size,
                    heif_file.data,
                    "raw",
                    heif_file.mode,
                    heif_file.stride,
                )
                
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
                try:
                    img = Image.open(image_path)
                except:
                    raise
        else:
            img = Image.open(image_path)
        
        if img is None:
            raise Exception("Failed to open image")
        
        if img.mode in ('RGBA', 'LA', 'P'):
            rgb_img = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'RGBA':
                rgb_img.paste(img, mask=img.split()[-1])
            elif img.mode == 'P':
                img = img.convert('RGBA')
                rgb_img.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            else:
                rgb_img.paste(img)
            img = rgb_img
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        
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
    
    format_mapping = {}
    for idx, item in enumerate(order.items):
        format_name = item.format_name
        folder_name = format_name.replace('/', '_').replace('\\', '_')
        folder_name = ''.join(c if c.isalnum() or c in '_-' else '_' for c in folder_name)
        
        format_mapping[str(idx)] = {
            'folder_name': folder_name,
            'display_name': format_name,
            'quantity': item.quantity
        }
    
    price_formats = {}
    for price in Price.query.filter_by(is_active=True).all():
        folder_name = price.format_name.replace('/', '_').replace('\\', '_')
        folder_name = ''.join(c if c.isalnum() or c in '_-' else '_' for c in folder_name)
        price_formats[price.format_key] = {
            'folder_name': folder_name,
            'display_name': price.format_name
        }
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        photos_by_format = {}
        
        for photo in order.photos:
            format_key = photo.format if photo.format else 'other'
            folder_name = None
            display_name = None
            
            if format_key.isdigit() and format_key in format_mapping:
                folder_name = format_mapping[format_key]['folder_name']
                display_name = format_mapping[format_key]['display_name']
            elif format_key in price_formats:
                folder_name = price_formats[format_key]['folder_name']
                display_name = price_formats[format_key]['display_name']
            else:
                found = False
                for idx, item in enumerate(order.items):
                    if item.format_name and item.format_name.lower() in format_key.lower():
                        folder_name = format_mapping[str(idx)]['folder_name']
                        display_name = format_mapping[str(idx)]['display_name']
                        found = True
                        break
                
                if not found:
                    folder_name = 'other_formats'
                    display_name = 'Другие форматы'
            
            if folder_name not in photos_by_format:
                photos_by_format[folder_name] = {
                    'photos': [],
                    'display_name': display_name
                }
            photos_by_format[folder_name]['photos'].append(photo)
        
        for folder_name, data in photos_by_format.items():
            photos = data['photos']
            display_name = data['display_name']
            
            logger.info(f"Creating folder '{folder_name}' for format '{display_name}' with {len(photos)} photos")
            
            for photo in photos:
                photo_path = os.path.join(app.config['UPLOAD_FOLDER'], photo.saved_filename)
                
                if os.path.exists(photo_path):
                    try:
                        original_name = os.path.splitext(photo.original_filename)[0]
                        original_name = secure_filename(original_name)
                        new_filename = f"{original_name}.jpg"
                        
                        if len(new_filename) > 200:
                            new_filename = f"{original_name[:150]}.jpg"
                        
                        jpg_bytes = convert_to_jpg_bytes(photo_path)
                        
                        if jpg_bytes:
                            archive_path = f"{folder_name}/{new_filename}"
                            zip_file.writestr(archive_path, jpg_bytes.getvalue())
                            logger.debug(f"Added {archive_path} to zip")
                        else:
                            logger.warning(f"Failed to convert {photo.original_filename}, adding original")
                            archive_path = f"{folder_name}/{photo.original_filename}"
                            zip_file.write(photo_path, archive_path)
                            
                    except Exception as e:
                        logger.error(f"Error processing photo {photo.original_filename}: {e}")
                        try:
                            archive_path = f"{folder_name}/{photo.original_filename}"
                            zip_file.write(photo_path, archive_path)
                        except Exception as write_err:
                            logger.error(f"Failed to add original file {photo.original_filename}: {write_err}")
                else:
                    logger.warning(f"Photo file not found: {photo_path}")
    
    zip_buffer.seek(0)
    return zip_buffer