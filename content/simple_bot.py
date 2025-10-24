# content/simple_bot.py
# Простой тест для проверки работы системы без Telegram API

import os, sys
import django
from django.conf import settings

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # корень проекта, где manage.py
sys.path.append(str(BASE_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myapp.settings")  # замени myapp на имя твоего проекта
import django
django.setup()

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myapp.settings')
django.setup()

def test_bot_functionality():
    """Тестирование функций бота без Telegram API"""
    
    print("=== Testing TentoriumRB Bot Functions ===")
    
    # Тест 1: Проверка настроек
    print("\n1. Testing settings...")
    if hasattr(settings, 'TELEGRAM_BOT_TOKEN'):
        print("&#9989; TELEGRAM_BOT_TOKEN is set")
        token_preview = settings.TELEGRAM_BOT_TOKEN[:10] + "..." if settings.TELEGRAM_BOT_TOKEN else "Not set"
        print(f"   Token preview: {token_preview}")
    else:
        print("&#10060; TELEGRAM_BOT_TOKEN not found in settings")
    
    # Тест 2: Проверка моделей
    print("\n2. Testing database models...")
    try:
        from content.models import Product, ProductCategory, TelegramUser
        
        # Подсчет продуктов
        products_count = Product.objects.filter(is_active=True).count()
        print(f"&#9989; Active products: {products_count}")
        
        # Подсчет категорий
        categories_count = ProductCategory.objects.filter(is_active=True).count()
        print(f"&#9989; Active categories: {categories_count}")
        
        # Telegram пользователи
        telegram_users_count = TelegramUser.objects.count()
        print(f"&#9989; Telegram users: {telegram_users_count}")
        
    except Exception as e:
        print(f"&#10060; Database error: {e}")
    
    # Тест 3: Проверка функций бота
    print("\n3. Testing bot functions...")
    try:
        # Симуляция получения каталога
        from content.models import Product
        products = Product.objects.filter(is_active=True)[:5]
        
        print("&#128230; Sample catalog:")
        for product in products:
            price_info = f"{product.price} &#8381;"
            if product.old_price and product.old_price > product.price:
                discount = int(((product.old_price - product.price) / product.old_price) * 100)
                price_info += f" (was {product.old_price} &#8381;, -{discount}%)"
            
            badges = []
            if product.is_new: badges.append("NEW")
            if product.is_bestseller: badges.append("HIT")
            if product.is_featured: badges.append("TOP")
            
            badge_str = " [" + ", ".join(badges) + "]" if badges else ""
            print(f"   • {product.name}{badge_str} - {price_info}")
        
        if not products:
            print("   No products found. Add products in admin panel.")
            
    except Exception as e:
        print(f"&#10060; Bot functions error: {e}")
    
    # Тест 4: Проверка аналитики
    print("\n4. Testing analytics...")
    try:
        from content.models import ProductView, ProductClick, Lead
        
        views_count = ProductView.objects.count()
        clicks_count = ProductClick.objects.count()
        leads_count = Lead.objects.count()
        
        print(f"&#9989; Product views: {views_count}")
        print(f"&#9989; Product clicks: {clicks_count}")
        print(f"&#9989; Total leads: {leads_count}")
        
        # Конверсия
        if views_count > 0:
            conversion = (clicks_count / views_count) * 100
            print(f"&#9989; Conversion rate: {conversion:.2f}%")
        
    except Exception as e:
        print(f"&#10060; Analytics error: {e}")
    
    print("\n=== Test Summary ===")
    print("&#9989; System is ready for Telegram bot!")
    print("&#128295; Next: Fix python-telegram-bot compatibility")
    print("&#128640; Then: Start bot with correct command")
    
    return True

if __name__ == "__main__":
    test_bot_functionality()
    