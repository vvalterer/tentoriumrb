# content/telegram_bot.py
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters, CallbackContext
from django.conf import settings
from django.core.management.base import BaseCommand

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self):
        if not hasattr(settings, 'TELEGRAM_BOT_TOKEN') or not settings.TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN не задан в settings.py")
        
        self.updater = Updater(token=settings.TELEGRAM_BOT_TOKEN, use_context=True)
        self.dispatcher = self.updater.dispatcher
        self.setup_handlers()
    
    def setup_handlers(self):
        """Настройка обработчиков команд и сообщений"""
        # Команды
        self.dispatcher.add_handler(CommandHandler("start", self.start))
        self.dispatcher.add_handler(CommandHandler("help", self.help_command))
        self.dispatcher.add_handler(CommandHandler("catalog", self.catalog))
        self.dispatcher.add_handler(CommandHandler("categories", self.categories))
        self.dispatcher.add_handler(CommandHandler("bestsellers", self.bestsellers))
        self.dispatcher.add_handler(CommandHandler("new", self.new_products))
        self.dispatcher.add_handler(CommandHandler("contact", self.contact))
        
        # Callback обработчики (кнопки)
        self.dispatcher.add_handler(CallbackQueryHandler(self.button_handler))
        
        # Обработка текстовых сообщений
        self.dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, self.handle_message))

    def start(self, update: Update, context: CallbackContext):
        """Стартовая команда"""
        user = update.effective_user
        
        # Сохраняем пользователя в БД
        self.save_telegram_user(user)
        
        welcome_text = f"""
&#127855; *Добро пожаловать в ТенториумРБ!*

Привет, {user.first_name}! 
Я бот для заказа натуральных продуктов пчеловодства.

&#127775; *Что я умею:*
• Показать каталог товаров
• Найти продукты по категориям  
• Показать хиты продаж и новинки
• Предоставить контакты для заказа

&#128203; *Основные команды:*
/catalog - Весь каталог
/categories - Категории товаров
/bestsellers - Хиты продаж
/new - Новинки
/contact - Контакты для заказа
/help - Помощь

Или просто напишите название товара для поиска! &#128269;
        """
        
        keyboard = [
            [
                InlineKeyboardButton("&#128230; Каталог", callback_data="catalog"),
                InlineKeyboardButton("&#127991;&#65039; Категории", callback_data="categories")
            ],
            [
                InlineKeyboardButton("&#128293; Хиты продаж", callback_data="bestsellers"),
                InlineKeyboardButton("&#10024; Новинки", callback_data="new")
            ],
            [
                InlineKeyboardButton("&#127760; Наш сайт", url="https://tentoriumrb.ru"),
                InlineKeyboardButton("&#128222; Контакты", callback_data="contact")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        update.message.reply_text(welcome_text, parse_mode='Markdown', reply_markup=reply_markup)

    def catalog(self, update: Update, context: CallbackContext):
        """Показать каталог товаров"""
        from content.models import Product
        
        products = Product.objects.filter(is_active=True).order_by('order', '-created_at')[:10]
        
        if not products:
            update.message.reply_text("&#129335;&#8205;&#9794;&#65039; Товары временно недоступны. Попробуйте позже.")
            return
        
        text = "&#128230; *Каталог товаров ТенториумРБ:*\n\n"
        keyboard = []
        
        for product in products:
            price_text = f"{product.price} &#8381;"
            if product.old_price and product.old_price > product.price:
                discount = int(((product.old_price - product.price) / product.old_price) * 100)
                price_text = f"~~{product.old_price} &#8381;~~ *{product.price} &#8381;* (-{discount}%)"
            
            badges = ""
            if product.is_new: badges += "&#10024; "
            if product.is_bestseller: badges += "&#128293; "
            if product.is_featured: badges += "&#11088; "
            
            text += f"{badges}*{product.name}*\n"
            text += f"&#128176; {price_text}\n"
            text += f"&#128221; {product.short_description[:60]}...\n\n"
            
            keyboard.append([
                InlineKeyboardButton(f"&#128722; {product.name}", callback_data=f"product_{product.id}")
            ])
        
        keyboard.append([
            InlineKeyboardButton("&#127760; Полный каталог на сайте", url="https://tentoriumrb.ru/products/")
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text(text, parse_mode='Markdown', reply_markup=reply_markup)

    def categories(self, update: Update, context: CallbackContext):
        """Показать категории товаров"""
        from content.models import ProductCategory
        
        categories = ProductCategory.objects.filter(is_active=True).order_by('order')
        
        text = "&#127991;&#65039; *Категории товаров:*\n\n"
        keyboard = []
        
        for category in categories:
            products_count = category.products.filter(is_active=True).count()
            text += f"• *{category.name}* ({products_count} товаров)\n"
            if category.description:
                text += f"  _{category.description}_\n"
            text += "\n"
            
            keyboard.append([
                InlineKeyboardButton(f"&#128230; {category.name}", callback_data=f"category_{category.id}")
            ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text(text, parse_mode='Markdown', reply_markup=reply_markup)

    def bestsellers(self, update: Update, context: CallbackContext):
        """Показать хиты продаж"""
        from content.models import Product
        
        products = Product.objects.filter(is_active=True, is_bestseller=True).order_by('order', '-created_at')[:8]
        self.send_products_list(update, products, "&#128293; *Хиты продаж:*\n\n")

    def new_products(self, update: Update, context: CallbackContext):
        """Показать новинки"""
        from content.models import Product
        
        products = Product.objects.filter(is_active=True, is_new=True).order_by('-created_at')[:8]
        self.send_products_list(update, products, "&#10024; *Новинки:*\n\n")

    def contact(self, update: Update, context: CallbackContext):
        """Показать контактную информацию"""
        text = """
&#128222; *Контакты ТенториумРБ*

*Для заказов и консультаций:*

&#128241; *Телефон:* +7 (347) 123-45-67
&#128231; *Email:* info@tentoriumrb.ru  
&#128172; *WhatsApp:* +7 (347) 123-45-67

&#127760; *Наш сайт:* https://tentoriumrb.ru

&#9200; *Режим работы:*
Пн-Вс: 09:00 - 21:00

&#128666; *Доставка по всей России!*

Мы работаем с продуктами компании Тенториум более 5 лет. 
Гарантируем качество и подлинность всех товаров! &#9989;
        """
        
        keyboard = [
            [
                InlineKeyboardButton("&#128222; Позвонить", url="tel:+73471234567"),
                InlineKeyboardButton("&#128172; WhatsApp", url="https://wa.me/73471234567")
            ],
            [
                InlineKeyboardButton("&#127760; Наш сайт", url="https://tentoriumrb.ru"),
                InlineKeyboardButton("&#128231; Написать email", url="mailto:info@tentoriumrb.ru")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text(text, parse_mode='Markdown', reply_markup=reply_markup)

    def help_command(self, update: Update, context: CallbackContext):
        """Помощь"""
        text = """
&#10067; *Помощь по использованию бота*

*Доступные команды:*
/start - Начать работу с ботом
/catalog - Показать каталог товаров
/categories - Категории продуктов
/bestsellers - Хиты продаж
/new - Новинки
/contact - Контактная информация
/help - Эта справка

*Как использовать:*
• Используйте команды или кнопки меню
• Напишите название товара для поиска
• Нажмите "Купить" для перехода на сайт заказа

*Нужна помощь?*
Напишите нам: info@tentoriumrb.ru
Или позвоните: +7 (347) 123-45-67
        """
        update.message.reply_text(text, parse_mode='Markdown')

    def button_handler(self, update: Update, context: CallbackContext):
        """Обработка нажатий на кнопки"""
        query = update.callback_query
        query.answer()
        
        data = query.data
        
        if data == "catalog":
            self.handle_catalog_callback(query)
        elif data == "categories":
            self.handle_categories_callback(query)
        elif data == "bestsellers":
            self.handle_bestsellers_callback(query)
        elif data == "new":
            self.handle_new_callback(query)
        elif data == "contact":
            self.handle_contact_callback(query)
        elif data.startswith("product_"):
            product_id = int(data.split("_")[1])
            self.show_product_detail(query, product_id)
        elif data.startswith("category_"):
            category_id = int(data.split("_")[1])
            self.show_category_products(query, category_id)
        elif data.startswith("buy_"):
            product_id = int(data.split("_")[1])
            self.handle_buy_product(query, product_id)

    def show_product_detail(self, query, product_id):
        """Показать детали товара"""
        from content.models import Product, ProductView
        
        try:
            product = Product.objects.get(id=product_id, is_active=True)
        except Product.DoesNotExist:
            query.edit_message_text("&#10060; Товар не найден.")
            return
        
        # Увеличиваем счетчик просмотров
        product.views_count += 1
        product.save(update_fields=['views_count'])
        
        # Записываем в аналитику
        try:
            ProductView.objects.create(
                product=product,
                ip_address='127.0.0.1',  # Telegram
                user_agent='Telegram Bot',
                referrer='telegram'
            )
        except:
            pass
        
        price_text = f"{product.price} &#8381;"
        if product.old_price and product.old_price > product.price:
            discount = int(((product.old_price - product.price) / product.old_price) * 100)
            price_text = f"~~{product.old_price} &#8381;~~ *{product.price} &#8381;* &#128293;(-{discount}%)"
        
        badges = ""
        if product.is_new: badges += "&#10024; "
        if product.is_bestseller: badges += "&#128293; "
        if product.is_featured: badges += "&#11088; "
        
        text = f"""
{badges}*{product.name}*

&#128176; *Цена:* {price_text}
&#127991;&#65039; *Категория:* {product.category.name}
"""
        
        if product.weight:
            text += f"&#128207; *Вес/объем:* {product.weight}\n"
        
        text += f"\n&#128221; *Описание:*\n{product.short_description}\n"
        
        if product.benefits:
            text += f"\n&#128138; *Полезные свойства:*\n{product.benefits[:200]}...\n"
        
        text += f"\n&#128065;&#65039; Просмотров: {product.views_count}"
        
        keyboard = [
            [InlineKeyboardButton("&#128722; Купить товар", callback_data=f"buy_{product.id}")],
            [InlineKeyboardButton("&#127760; Подробнее на сайте", url=f"https://tentoriumrb.ru/product/{product.id}/")],
            [InlineKeyboardButton("&#11013;&#65039; Назад к каталогу", callback_data="catalog")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)

    def handle_buy_product(self, query, product_id):
        """Обработка покупки товара"""
        from content.models import Product, ProductClick, Lead, TelegramUser
        
        try:
            product = Product.objects.get(id=product_id, is_active=True)
        except Product.DoesNotExist:
            query.edit_message_text("&#10060; Товар не найден.")
            return
        
        user = query.from_user
        
        # Увеличиваем счетчик кликов
        product.clicks_count += 1
        product.save(update_fields=['clicks_count'])
        
        # Записываем клик в аналитику
        try:
            ProductClick.objects.create(
                product=product,
                ip_address='127.0.0.1',  # Telegram
                user_agent='Telegram Bot',
                referrer='telegram'
            )
        except:
            pass
        
        # Создаем лид
        try:
            telegram_user, created = TelegramUser.objects.get_or_create(
                user_id=user.id,
                defaults={
                    'username': user.username,
                    'first_name': user.first_name,
                    'last_name': user.last_name or '',
                    'is_active': True
                }
            )
            
            Lead.objects.create(
                name=f"{user.first_name} {user.last_name or ''}".strip(),
                phone=f"Telegram: @{user.username}" if user.username else f"Telegram ID: {user.id}",
                email=f"telegram_user_{user.id}@telegram.local",
                message=f"Интерес к товару: {product.name} через Telegram бот",
                source='telegram',
                telegram_user=telegram_user,
                product_interest=product
            )
        except:
            pass
        
        text = f"""
&#128722; *Оформление заказа: {product.name}*

Для покупки товара свяжитесь с нами любым удобным способом:

&#128222; *Телефон:* +7 (347) 123-45-67
&#128231; *Email:* info@tentoriumrb.ru
&#128172; *WhatsApp:* +7 (347) 123-45-67

&#127760; *Или оформите заказ на сайте:*
{product.referral_url}

&#128176; *Цена:* {product.price} &#8381;
&#128230; *Товар:* {product.name}

Наш менеджер свяжется с вами в ближайшее время! &#9989;
        """
        
        keyboard = [
            [InlineKeyboardButton("&#127760; Купить на сайте", url=product.referral_url)],
            [InlineKeyboardButton("&#128222; Позвонить", url="tel:+73471234567")],
            [InlineKeyboardButton("&#128172; WhatsApp", url="https://wa.me/73471234567")],
            [InlineKeyboardButton("&#11013;&#65039; Назад к товару", callback_data=f"product_{product_id}")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)

    def handle_message(self, update: Update, context: CallbackContext):
        """Обработка текстовых сообщений (поиск)"""
        from content.models import Product
        
        query_text = update.message.text.lower()
        
        # Поиск товаров
        products = Product.objects.filter(
            name__icontains=query_text,
            is_active=True
        )[:8]
        
        if products:
            text = f"&#128269; *Результаты поиска '{update.message.text}':*\n\n"
            self.send_products_list(update, products, text, is_search=True)
        else:
            text = f"""
&#129335;&#8205;&#9794;&#65039; По запросу "*{update.message.text}*" ничего не найдено.

Попробуйте:
• /catalog - посмотреть весь каталог
• /categories - выбрать категорию
• Написать более общий запрос (например: "мед", "прополис")
            """
            
            keyboard = [
                [InlineKeyboardButton("&#128230; Весь каталог", callback_data="catalog")],
                [InlineKeyboardButton("&#127991;&#65039; Категории", callback_data="categories")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            update.message.reply_text(text, parse_mode='Markdown', reply_markup=reply_markup)

    def send_products_list(self, update, products, header_text, is_search=False):
        """Отправить список товаров"""
        if not products:
            text = "&#129335;&#8205;&#9794;&#65039; Товары не найдены."
            if is_search:
                text = "&#128269; По вашему запросу товары не найдены."
            update.message.reply_text(text)
            return
        
        text = header_text
        keyboard = []
        
        for product in products[:8]:  # Показываем максимум 8 товаров
            price_text = f"{product.price} &#8381;"
            if product.old_price and product.old_price > product.price:
                discount = int(((product.old_price - product.price) / product.old_price) * 100)
                price_text = f"~~{product.old_price} &#8381;~~ *{product.price} &#8381;* (-{discount}%)"
            
            badges = ""
            if product.is_new: badges += "&#10024; "
            if product.is_bestseller: badges += "&#128293; "
            if product.is_featured: badges += "&#11088; "
            
            text += f"{badges}*{product.name}*\n"
            text += f"&#128176; {price_text}\n\n"
            
            keyboard.append([
                InlineKeyboardButton(f"&#128722; {product.name[:25]}...", callback_data=f"product_{product.id}")
            ])
        
        if len(products) > 8:
            text += f"... и еще {len(products) - 8} товаров\n\n"
        
        keyboard.append([
            InlineKeyboardButton("&#127760; Полный каталог", url="https://tentoriumrb.ru/products/")
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text(text, parse_mode='Markdown', reply_markup=reply_markup)

    def save_telegram_user(self, user):
        """Сохранение пользователя Telegram в БД"""
        from content.models import TelegramUser
        
        try:
            telegram_user, created = TelegramUser.objects.get_or_create(
                user_id=user.id,
                defaults={
                    'username': user.username,
                    'first_name': user.first_name,
                    'last_name': user.last_name or '',
                    'is_active': True
                }
            )
            if not created:
                # Обновляем информацию о пользователе
                telegram_user.username = user.username
                telegram_user.first_name = user.first_name
                telegram_user.last_name = user.last_name or ''
                telegram_user.save()
        except Exception as e:
            logger.error(f"Ошибка сохранения пользователя Telegram: {e}")

    # Упрощенные обработчики callback для совместимости
    def handle_catalog_callback(self, query):
        # Создаем fake update для совместимости
        fake_update = type('obj', (object,), {'message': query.message})()
        self.catalog(fake_update, None)

    def handle_categories_callback(self, query):
        fake_update = type('obj', (object,), {'message': query.message})()
        self.categories(fake_update, None)

    def handle_bestsellers_callback(self, query):
        fake_update = type('obj', (object,), {'message': query.message})()
        self.bestsellers(fake_update, None)

    def handle_new_callback(self, query):
        fake_update = type('obj', (object,), {'message': query.message})()
        self.new_products(fake_update, None)

    def handle_contact_callback(self, query):
        fake_update = type('obj', (object,), {'message': query.message})()
        self.contact(fake_update, None)

    def show_category_products(self, query, category_id):
        from content.models import ProductCategory
        
        try:
            category = ProductCategory.objects.get(id=category_id, is_active=True)
            products = category.products.filter(is_active=True)[:8]
            
            fake_update = type('obj', (object,), {'message': query.message})()
            self.send_products_list(fake_update, products, f"&#128230; *{category.name}:*\n\n")
        except ProductCategory.DoesNotExist:
            query.edit_message_text("&#10060; Категория не найдена.")

    def run(self):
        """Запуск бота"""
        logger.info("Запуск Telegram бота ТенториумРБ...")
        self.updater.start_polling()
        self.updater.idle()


# Django команда для запуска бота
class Command(BaseCommand):
    help = 'Запуск Telegram бота ТенториумРБ'

    def handle(self, *args, **options):
        bot = TelegramBot()
        bot.run()
        