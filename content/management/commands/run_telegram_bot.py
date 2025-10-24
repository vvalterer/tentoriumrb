# -*- coding: utf-8 -*-
"""
Улучшенный Telegram бот для Django приложения
Совместимо с Python 3.6+ и python-telegram-bot v13.11
Интеграция с существующими Django моделями
"""

import io
import sys
import os
import logging
import time
import re
from typing import Dict, List, Optional, Tuple
from html import escape as esc

# ---------- Починка stdout/stderr для Python 3.6 (UTF-8) ----------
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "buffer"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ---------- Django bootstrap ----------
import django
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections, OperationalError, connections

if "DJANGO_SETTINGS_MODULE" not in os.environ:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myapp.settings")

if not settings.configured:
    django.setup()

# ---------- Telegram ----------
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler
from telegram.ext import Filters

# ---------- Логирование ----------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# ---------- DB safety decorator ----------
def db_safe(func):
    def wrapper(*args, **kwargs):
        try:
            close_old_connections()
            return func(*args, **kwargs)
        except OperationalError as e:
            logger.warning("DB reconnect after OperationalError: %s", e)
            try:
                for conn in connections.all():
                    try:
                        conn.close()
                    except Exception:
                        pass
            except Exception:
                pass
            time.sleep(0.5)
            close_old_connections()
            return func(*args, **kwargs)
        except Exception as e:
            logger.error("Unexpected error in %s: %s", func.__name__, e)
            raise
        finally:
            try:
                close_old_connections()
            except Exception:
                pass
    return wrapper


class ImprovedTelegramBot:
    def __init__(self):
        if not getattr(settings, "TELEGRAM_BOT_TOKEN", None):
            raise ValueError("TELEGRAM_BOT_TOKEN not set in settings.py")

        # Настройки пагинации для улучшенного UX
        self.PRODUCTS_PER_PAGE = 6
        self.CATEGORIES_PER_PAGE = 8

        # Кэш для оптимизации (пока не используется, оставлено на будущее)
        self.search_cache = {}
        self.category_cache = {}

        # Эмодзи для различных типов товаров (как HTML-сущности для текста сообщений)
        self.CATEGORY_EMOJIS = {
            'мед': '&#127855;', 'мёд': '&#127855;', 'honey': '&#127855;',
            'прополис': '&#128996;', 'propolis': '&#128996;',
            'пыльца': '&#127804;', 'перга': '&#127804;', 'pollen': '&#127804;',
            'маточное молочко': '&#128081;', 'royal jelly': '&#128081;',
            'воск': '&#128367;&#65039;', 'wax': '&#128367;&#65039;',
            'косметика': '&#128133;', 'cosmetics': '&#128133;',
            'бад': '&#128138;', 'драже': '&#128138;', 'supplements': '&#128138;',
            'чай': '&#127861;', 'tea': '&#127861;',
            'крем': '&#129524;', 'cream': '&#129524;',
            'масло': '&#129746;', 'oil': '&#129746;',
        }

        # Проверим доступность моделей
        try:
            from content.models import Product, ProductCategory, TelegramUser  # noqa
            self.models_available = True
            logger.info("Django модели успешно импортированы")
        except Exception as e:
            logger.error("Ошибка импорта моделей: %s", e)
            self.models_available = False

        self.updater = Updater(token=settings.TELEGRAM_BOT_TOKEN, use_context=True)
        self.dispatcher = self.updater.dispatcher
        self._setup_handlers()

    def _setup_handlers(self):
        """Настройка обработчиков команд с улучшенной навигацией"""
        dp = self.dispatcher

        # Основные команды
        dp.add_handler(CommandHandler("start", self.start))
        dp.add_handler(CommandHandler("help", self.help_command))
        dp.add_handler(CommandHandler("catalog", self.catalog_with_pagination))
        dp.add_handler(CommandHandler("categories", self.categories_with_pagination))
        dp.add_handler(CommandHandler("bestsellers", self.bestsellers))
        dp.add_handler(CommandHandler("new", self.new_products))
        dp.add_handler(CommandHandler("discounts", self.discounts))
        dp.add_handler(CommandHandler("contact", self.contact))
        dp.add_handler(CommandHandler("about", self.about))
        dp.add_handler(CommandHandler("search", self.search_help))

        # Обработчики кнопок и поиска
        dp.add_handler(CallbackQueryHandler(self.enhanced_button_handler))
        dp.add_handler(MessageHandler(Filters.text & ~Filters.command, self.smart_search))

    @db_safe
    def check_models(self):
        """Проверка доступности Django моделей и БД"""
        if not self.models_available:
            return False
        try:
            from content.models import Product  # noqa
            # Лёгкий запрос, чтобы убедиться в коннекте
            Product.objects.first()
            return True
        except Exception as e:
            logger.error("Ошибка доступа к БД: %s", e)
            return False

    def get_category_emoji(self, category_name: str) -> str:
        """Получение эмодзи для категории на основе названия"""
        if not category_name:
            return "&#128230;"
        name_lower = category_name.lower()
        for key, emoji in self.CATEGORY_EMOJIS.items():
            if key in name_lower:
                return emoji
        return "&#128230;"  # По умолчанию

    # ---------- Универсальная отправка/редактирование ----------
    def _send_or_edit_message(self, update: Update, text: str, reply_markup):
        """Универсальная отправка или редактирование сообщения (safe)"""
        try:
            msg = getattr(update, "message", None)
            cq = getattr(update, "callback_query", None)
            if msg is not None:
                msg.reply_text(text, parse_mode="HTML", reply_markup=reply_markup)
            elif cq is not None:
                cq.edit_message_text(text, parse_mode="HTML", reply_markup=reply_markup)
            else:
                logger.warning("Нет ни message, ни callback_query в update – нечего отправлять.")
        except Exception as e:
            logger.error("Ошибка отправки/редактирования сообщения: %s", e)

    def _send_error_message(self, update: Update, message: str):
        """Отправка сообщения об ошибке"""
        text = f"&#9888;&#65039; {message}. Попробуйте позже."
        keyboard = [[InlineKeyboardButton("&#127968; Главная", callback_data="start")]]
        self._send_or_edit_message(update, text, InlineKeyboardMarkup(keyboard))

    # ---------- Главное меню и стартовая команда ----------
    def start(self, update: Update, context):
        """Улучшенное стартовое меню с красивым дизайном"""
        user = update.effective_user
        self.save_telegram_user(user)

        fn = esc(user.first_name or "")
        welcome_text = (
            f"&#127855; <b>Добро пожаловать в ТенториумРБ, {fn}!</b>\n\n"
            "&#127775; <i>Натуральные продукты пчеловодства высшего качества</i>\n\n"
            "&#128640; <b>Быстрый доступ:</b>\n"
            "• &#128218; Просмотр по категориям\n"
            "• &#128293; Популярные товары\n"
            "• &#11088; Новинки и скидки\n"
            "• &#128269; Умный поиск товаров\n\n"
            "&#128172; Просто напишите название товара для поиска!\n"
            "&#128222; Или выберите действие из меню ниже:"
        )

        keyboard = self.get_enhanced_main_menu()
        self._send_or_edit_message(update, welcome_text, keyboard)

    def get_enhanced_main_menu(self) -> InlineKeyboardMarkup:
        """Улучшенное главное меню с иконками и группировкой"""
        keyboard = [
            [
                InlineKeyboardButton("&#128218; Категории", callback_data="categories_0"),
                InlineKeyboardButton("&#128293; Хиты продаж", callback_data="hits_0"),
            ],
            [
                InlineKeyboardButton("&#11088; Новинки", callback_data="new_0"),
                InlineKeyboardButton("&#128176; Скидки", callback_data="discounts_0"),
            ],
            [
                InlineKeyboardButton("&#128269; Поиск товаров", callback_data="search_help"),
                InlineKeyboardButton("&#128203; Весь каталог", callback_data="catalog_0"),
            ],
            [
                InlineKeyboardButton("&#127970; О компании", callback_data="about"),
                InlineKeyboardButton("&#128222; Контакты", callback_data="contact"),
            ],
        ]
        return InlineKeyboardMarkup(keyboard)

    # ---------- Каталог с пагинацией ----------
    @db_safe
    def catalog_with_pagination(self, update: Update, context, page: int = 0):
        """Каталог товаров с пагинацией и улучшенным отображением"""
        if not self.check_models():
            self._send_error_message(update, "Каталог временно недоступен")
            return

        try:
            from content.models import Product

            offset = page * self.PRODUCTS_PER_PAGE
            products = Product.objects.filter(is_active=True).order_by("order", "-created_at")[
                offset : offset + self.PRODUCTS_PER_PAGE
            ]
            total_products = Product.objects.filter(is_active=True).count()
            total_pages = (total_products + self.PRODUCTS_PER_PAGE - 1) // self.PRODUCTS_PER_PAGE

        except Exception as e:
            logger.error("Ошибка загрузки каталога: %s", e)
            self._send_error_message(update, "Ошибка загрузки каталога")
            return

        if not products and page == 0:
            text = "&#128230; Товары временно недоступны."
            keyboard = [[InlineKeyboardButton("&#127968; Главная", callback_data="start")]]
        else:
            text = f"&#128203; <b>Каталог продукции</b> (стр. {page + 1} из {max(total_pages,1)})\n\n"
            keyboard = []
            for product in products:
                name = esc(product.name)
                price_text = self._format_price(product)
                badges = self._get_product_badges(product)
                text += f"{badges}<b>{name}</b>\n&#128176; {price_text}\n\n"
                btn_text = name[:30] + "..." if len(name) > 30 else name
                keyboard.append([InlineKeyboardButton(f"&#128722; {btn_text}", callback_data=f"product_{product.id}")])

            nav_buttons = []
            if page > 0:
                nav_buttons.append(InlineKeyboardButton("&#9664;&#65039; Пред", callback_data=f"catalog_{page-1}"))
            if page < total_pages - 1:
                nav_buttons.append(InlineKeyboardButton("След &#9654;&#65039;", callback_data=f"catalog_{page+1}"))
            if nav_buttons:
                keyboard.append(nav_buttons)
            keyboard.append([InlineKeyboardButton("&#127968; Главная", callback_data="start")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        self._send_or_edit_message(update, text, reply_markup)

    # ---------- Категории с пагинацией ----------
    @db_safe
    def categories_with_pagination(self, update: Update, context, page: int = 0):
        """Показ категорий с пагинацией и счетчиками товаров"""
        if not self.check_models():
            self._send_error_message(update, "Категории временно недоступны")
            return

        try:
            from content.models import ProductCategory

            offset = page * self.CATEGORIES_PER_PAGE
            categories = ProductCategory.objects.filter(is_active=True).order_by("order")[
                offset : offset + self.CATEGORIES_PER_PAGE
            ]
            total_categories = ProductCategory.objects.filter(is_active=True).count()
            total_pages = (total_categories + self.CATEGORIES_PER_PAGE - 1) // self.CATEGORIES_PER_PAGE

        except Exception as e:
            logger.error("Ошибка загрузки категорий: %s", e)
            self._send_error_message(update, "Ошибка загрузки категорий")
            return

        if not categories:
            text = "&#128194; Категории не найдены."
            keyboard = [[InlineKeyboardButton("&#127968; Главная", callback_data="start")]]
        else:
            text = f"&#128218; <b>Категории товаров</b> (стр. {page + 1} из {max(total_pages,1)})\n\nВыберите категорию:\n\n"
            keyboard = []

            for i in range(0, len(categories), 2):
                row = []
                for j in range(i, min(i + 2, len(categories))):
                    category = categories[j]
                    try:
                        product_count = category.products.filter(is_active=True).count()
                    except Exception:
                        product_count = 0
                    emoji = self.get_category_emoji(category.name)
                    btn_text = f"{emoji} {category.name} ({product_count})"
                    if len(btn_text) > 25:
                        btn_text = f"{emoji} {category.name[:20]}... ({product_count})"
                    row.append(InlineKeyboardButton(btn_text, callback_data=f"category_{category.id}_0"))
                keyboard.append(row)

            nav_buttons = []
            if page > 0:
                nav_buttons.append(InlineKeyboardButton("&#9664;&#65039; Пред", callback_data=f"categories_{page-1}"))
            if page < total_pages - 1:
                nav_buttons.append(InlineKeyboardButton("След &#9654;&#65039;", callback_data=f"categories_{page+1}"))
            if nav_buttons:
                keyboard.append(nav_buttons)

            keyboard.append([InlineKeyboardButton("&#127968; Главная", callback_data="start")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        self._send_or_edit_message(update, text, reply_markup)

    # ---------- Умный поиск ----------
    @db_safe
    def smart_search(self, update: Update, context):
        """Улучшенный поиск с нормализацией запросов и автодополнением"""
        if not self.check_models():
            self._send_error_message(update, "Поиск временно недоступен")
            return

        query_text_raw = (getattr(update.message, "text", "") or "").strip()
        if len(query_text_raw) < 2:
            update.message.reply_text(
                "&#128269; <b>Поиск слишком короткий</b>\n\n"
                "Введите минимум 2 символа для поиска.\n"
                "Например: <i>мед</i>, <i>прополис</i>, <i>крем</i>",
                parse_mode="HTML",
            )
            return

        try:
            from django.db import models as dj_models  # noqa
            from content.models import Product  # noqa

            query_text = self._normalize_search_query(query_text_raw)
            products = self._smart_product_search(query_text)

            if products:
                header = f"&#128269; <b>Найдено по запросу «{esc(query_text_raw)}»:</b>\n\n"
                self.send_products_list_enhanced(update, products, header, show_back=True, is_search=True)
                self._save_search_query(query_text_raw, len(products), update.effective_user.id)
            else:
                self._send_search_suggestions(update, query_text_raw)

        except Exception as e:
            logger.error("Ошибка поиска: %s", e)
            self._send_error_message(update, "Ошибка поиска")

    def _normalize_search_query(self, query: str) -> str:
        """Нормализация поискового запроса"""
        query = query.lower().strip()
        replacements = {
            'мед ': 'мёд ', ' мед': ' мёд', 'мед': 'мёд',
            'пчелиный': 'пчел', 'натуральный': '',
            'продукты пчеловодства': '', 'для иммунитета': 'иммун',
            'от простуды': 'простуд', 'для здоровья': 'здоров',
            'крема': 'крем', 'кремы': 'крем',
            'масла': 'масло', 'драже': 'драж',
        }
        for old, new in replacements.items():
            query = query.replace(old, new)
        return query.strip()

    def _smart_product_search(self, query: str):
        """Умный поиск товаров с ранжированием"""
        from django.db import models as dj_models
        from content.models import Product

        name_matches = Product.objects.filter(
            name__icontains=query, is_active=True
        ).order_by('-is_bestseller', '-is_new', 'order')[:4]

        if name_matches.count() >= 3:
            return name_matches

        extended_matches = Product.objects.filter(
            dj_models.Q(name__icontains=query) |
            dj_models.Q(short_description__icontains=query) |
            dj_models.Q(benefits__icontains=query),
            is_active=True
        ).exclude(
            id__in=[p.id for p in name_matches]
        ).order_by('-is_bestseller', '-is_new', 'order')[:6]

        all_products = list(name_matches) + list(extended_matches)
        return all_products[:6]

    def _send_search_suggestions(self, update: Update, query: str):
        """Отправка предложений при неудачном поиске"""
        text = (
            f"&#129335;&#8205;&#9794;&#65039; <b>По запросу «{esc(query)}» ничего не найдено</b>\n\n"
            "&#128161; <b>Попробуйте:</b>\n"
            "• Более общий запрос (например: <i>мёд</i>, <i>прополис</i>)\n"
            "• Проверьте правописание\n"
            "• Воспользуйтесь категориями\n\n"
            "&#128293; <b>Популярные запросы:</b>\n"
            "• Мёд алтайский\n"
            "• Прополис\n"
            "• Крем для лица\n"
            "• Драже для иммунитета"
        )

        keyboard = [
            [
                InlineKeyboardButton("&#128218; Категории", callback_data="categories_0"),
                InlineKeyboardButton("&#128293; Хиты", callback_data="hits_0"),
            ],
            [
                InlineKeyboardButton("&#128203; Весь каталог", callback_data="catalog_0"),
                InlineKeyboardButton("&#127968; Главная", callback_data="start"),
            ],
        ]
        update.message.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
        # ---------- Аналитика поиска (опционально) ----------
    def _save_search_query(self, query: str, results_count: int, user_id: int):
        """Опциональное сохранение поискового запроса для аналитики.
        Если соответствующей модели нет — тихо пропускаем.
        """
        try:
            from django.apps import apps
            Model = apps.get_model('content', 'SearchQuery')
            if not Model:
                return

            obj = Model()
            field_names = {f.name for f in Model._meta.get_fields()}

            if 'query' in field_names:
                setattr(obj, 'query', (query or '')[:255])
            if 'results_count' in field_names:
                setattr(obj, 'results_count', int(results_count))
            if 'telegram_user_id' in field_names:
                setattr(obj, 'telegram_user_id', int(user_id))
            if 'source' in field_names:
                setattr(obj, 'source', 'telegram')

            obj.save()
        except Exception as e:
            logger.debug("Search analytics not saved: %s", e)

    # ---------- Специальные фильтры ----------
    @db_safe
    def bestsellers(self, update: Update, context):
        """Хиты продаж"""
        self._show_filtered_products(update, 'bestseller', "&#128293; <b>Хиты продаж:</b>\n\n")

    @db_safe
    def new_products(self, update: Update, context):
        """Новинки"""
        self._show_filtered_products(update, 'new', "&#11088; <b>Новинки:</b>\n\n")

    @db_safe
    def discounts(self, update: Update, context):
        """Товары со скидками"""
        self._show_filtered_products(update, 'discount', "&#128176; <b>Скидки и акции:</b>\n\n")

    def _show_filtered_products(self, update: Update, filter_type: str, header: str):
        """Универсальный метод для показа отфильтрованных товаров"""
        if not self.check_models():
            self._send_error_message(update, "Товары временно недоступны")
            return

        try:
            from content.models import Product
            from django.db import models as dj_models  # noqa

            if filter_type == 'bestseller':
                products = Product.objects.filter(is_active=True, is_bestseller=True)
            elif filter_type == 'new':
                products = Product.objects.filter(is_active=True, is_new=True)
            elif filter_type == 'discount':
                products = Product.objects.filter(
                    is_active=True,
                    old_price__isnull=False,
                    old_price__gt=dj_models.F('price')
                )
            else:
                products = Product.objects.filter(is_active=True)

            products = products.order_by('order', '-created_at')[:8]

        except Exception as e:
            logger.error(f"Ошибка загрузки {filter_type}: %s", e)
            self._send_error_message(update, f"Ошибка загрузки")
            return

        self.send_products_list_enhanced(update, products, header, show_back=True)

    # ---------- Вспомогательные методы ----------
    def _format_price(self, product) -> str:
        """Форматирование цены с учетом скидок"""
        price_text = f"{product.price:,.0f} &#8381;".replace(",", " ")
        if hasattr(product, 'old_price') and product.old_price and product.old_price > product.price:
            discount = int(((product.old_price - product.price) / product.old_price) * 100)
            old_price_text = f"{product.old_price:,.0f} &#8381;".replace(",", " ")
            new_price_text = f"{product.price:,.0f} &#8381;".replace(",", " ")
            price_text = f"<s>{old_price_text}</s> <b>{new_price_text}</b> &#128293;(-{discount}%)"
        return price_text

    def _get_product_badges(self, product) -> str:
        """Получение бейджей товара"""
        badges = ""
        if getattr(product, 'is_new', False):
            badges += "&#11088; "
        if getattr(product, 'is_bestseller', False):
            badges += "&#128293; "
        if getattr(product, 'is_featured', False):
            badges += "&#11088; "
        return badges

    # ---------- Отправка списка товаров ----------
    def send_products_list_enhanced(self, update: Update, products, header_text: str,
                                    show_back: bool = False, is_search: bool = False):
        """Улучшенная отправка списка товаров (safe)"""
        if not products:
            text = "&#128269; По вашему запросу товары не найдены." if is_search else "&#128230; Товары не найдены."
            keyboard = [
                [InlineKeyboardButton("&#128218; Категории", callback_data="categories_0")],
                [InlineKeyboardButton("&#127968; Главная", callback_data="start")],
            ]
            self._send_or_edit_message(update, text, InlineKeyboardMarkup(keyboard))
            return

        text = header_text
        keyboard = []

        for product in products[:self.PRODUCTS_PER_PAGE]:
            name = esc(product.name)
            price_text = self._format_price(product)
            badges = self._get_product_badges(product)

            short_desc = ""
            if hasattr(product, 'short_description') and product.short_description:
                short_desc = esc(product.short_description)
                if len(short_desc) > 60:
                    short_desc = short_desc[:60] + "..."

            text += f"{badges}<b>{name}</b>\n"
            text += f"&#128176; {price_text}\n"
            if short_desc:
                text += f"&#128221; {short_desc}\n"
            text += "\n"

            btn_name = name[:25] + "..." if len(name) > 25 else name
            keyboard.append([InlineKeyboardButton(f"&#128722; {btn_name}", callback_data=f"product_{product.id}")])

        if show_back:
            keyboard.append([InlineKeyboardButton("&#128281; Назад", callback_data="start")])

        self._send_or_edit_message(update, text, InlineKeyboardMarkup(keyboard))

    # ---------- Обработка кнопок ----------
    def enhanced_button_handler(self, update: Update, context):
        """Улучшенный обработчик кнопок с поддержкой пагинации (без фейковых апдейтов)"""
        query = update.callback_query
        query.answer()
        data = query.data

        try:
            if data == "start":
                self.start(update, context)

            elif data.startswith("catalog_"):
                page = int(data.split("_")[1])
                self.catalog_with_pagination(update, context, page)

            elif data.startswith("categories_"):
                page = int(data.split("_")[1])
                self.categories_with_pagination(update, context, page)

            elif data.startswith("category_"):
                parts = data.split("_")
                category_id, page = int(parts[1]), int(parts[2])
                # Здесь именно редактируем текущее сообщение через query
                self.show_category_products_paginated(query, category_id, page)

            elif data.startswith("hits_"):
                self.bestsellers(update, context)

            elif data.startswith("new_"):
                self.new_products(update, context)

            elif data.startswith("discounts_"):
                self.discounts(update, context)

            elif data == "search_help":
                self.search_help(update, context)

            elif data == "contact":
                self.contact(update, context)

            elif data == "about":
                self.about(update, context)

            elif data.startswith("product_"):
                product_id = int(data.split("_")[1])
                self.show_product_detail(query, product_id)

            elif data.startswith("buy_"):
                product_id = int(data.split("_")[1])
                self.handle_buy_product(query, product_id)

            else:
                query.edit_message_text("&#10067; Неизвестная команда", parse_mode="HTML")

        except Exception as e:
            logger.error("Ошибка в обработчике кнопок: %s", e)
            query.edit_message_text("&#9888;&#65039; Произошла ошибка. Попробуйте позже.", parse_mode="HTML")

    # ---------- Показ товаров категории ----------
    @db_safe
    def show_category_products_paginated(self, query, category_id: int, page: int = 0):
        """Показ товаров категории с пагинацией (через редактирование сообщения)"""
        if not self.check_models():
            query.edit_message_text("&#9888;&#65039; Категория временно недоступна.", parse_mode="HTML")
            return

        try:
            from content.models import ProductCategory

            category = ProductCategory.objects.get(id=category_id, is_active=True)
            offset = page * self.PRODUCTS_PER_PAGE
            products = category.products.filter(is_active=True).order_by('order', '-created_at')[
                offset : offset + self.PRODUCTS_PER_PAGE
            ]
            total_products = category.products.filter(is_active=True).count()
            total_pages = (total_products + self.PRODUCTS_PER_PAGE - 1) // self.PRODUCTS_PER_PAGE

        except ProductCategory.DoesNotExist:
            query.edit_message_text("&#10060; Категория не найдена.", parse_mode="HTML")
            return
        except Exception as e:
            logger.error("Ошибка загрузки товаров категории: %s", e)
            query.edit_message_text("&#9888;&#65039; Ошибка загрузки категории.", parse_mode="HTML")
            return

        if not products and page == 0:
            text = f"&#128230; В категории «{esc(category.name)}» пока нет товаров."
            keyboard = [
                [InlineKeyboardButton("&#128218; Другие категории", callback_data="categories_0")],
                [InlineKeyboardButton("&#127968; Главная", callback_data="start")],
            ]
        else:
            emoji = self.get_category_emoji(category.name)
            text = f"{emoji} <b>{esc(category.name)}</b>"
            if total_pages > 1:
                text += f" (стр. {page + 1} из {max(total_pages,1)})"
            text += "\n\n"

            keyboard = []
            for product in products:
                name = esc(product.name)
                price_text = self._format_price(product)
                badges = self._get_product_badges(product)
                text += f"{badges}<b>{name}</b>\n&#128176; {price_text}\n\n"
                btn_text = name[:30] + "..." if len(name) > 30 else name
                keyboard.append([InlineKeyboardButton(f"&#128722; {btn_text}", callback_data=f"product_{product.id}")])

            nav_buttons = []
            if page > 0:
                nav_buttons.append(InlineKeyboardButton("&#9664;&#65039; Пред", callback_data=f"category_{category_id}_{page-1}"))
            if page < total_pages - 1:
                nav_buttons.append(InlineKeyboardButton("След &#9654;&#65039;", callback_data=f"category_{category_id}_{page+1}"))
            if nav_buttons:
                keyboard.append(nav_buttons)

            keyboard.append([
                InlineKeyboardButton("&#128218; Категории", callback_data="categories_0"),
                InlineKeyboardButton("&#127968; Главная", callback_data="start"),
            ])

        query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

    # ---------- Детальная информация о товаре ----------
    @db_safe
    def show_product_detail(self, query, product_id: int):
        """Детальная информация о товаре (редактирование сообщения)"""
        if not self.check_models():
            query.edit_message_text("&#9888;&#65039; Товар временно недоступен.", parse_mode="HTML")
            return

        try:
            from content.models import Product, ProductView
            product = Product.objects.get(id=product_id, is_active=True)

        except Product.DoesNotExist:
            query.edit_message_text("&#10060; Товар не найден.", parse_mode="HTML")
            return
        except Exception as e:
            logger.error("Ошибка загрузки товара: %s", e)
            query.edit_message_text("&#9888;&#65039; Ошибка загрузки товара.", parse_mode="HTML")
            return

        # Увеличиваем счетчик просмотров
        try:
            if hasattr(product, 'views_count'):
                product.views_count = (product.views_count or 0) + 1
                product.save(update_fields=['views_count'])
            try:
                ProductView.objects.create(
                    product=product,
                    ip_address="127.0.0.1",
                    user_agent="Telegram Bot",
                    referrer="telegram",
                )
            except Exception:
                pass
        except Exception as e:
            logger.error("Ошибка сохранения статистики: %s", e)

        name = esc(product.name)
        price_text = self._format_price(product)
        badges = self._get_product_badges(product)

        text = f"{badges}<b>{name}</b>\n\n"
        text += f"&#128176; <b>Цена:</b> {price_text}\n"

        if hasattr(product, 'category') and product.category:
            cat_emoji = self.get_category_emoji(product.category.name)
            text += f"{cat_emoji} <b>Категория:</b> {esc(product.category.name)}\n"

        if hasattr(product, 'weight') and product.weight:
            text += f"&#9878;&#65039; <b>Вес/объем:</b> {esc(product.weight)}\n"

        text += "\n"

        if hasattr(product, 'short_description') and product.short_description:
            desc = esc(product.short_description)
            if len(desc) > 300:
                desc = desc[:300] + "..."
            text += f"&#128221; <b>Описание:</b>\n{desc}\n\n"

        if hasattr(product, 'benefits') and product.benefits:
            benefits = esc(product.benefits)
            if len(benefits) > 200:
                benefits = benefits[:200] + "..."
            text += f"&#10024; <b>Полезные свойства:</b>\n{benefits}\n\n"

        stats = []
        if hasattr(product, 'views_count') and product.views_count:
            stats.append(f"&#128065; {product.views_count}")
        if hasattr(product, 'clicks_count') and product.clicks_count:
            stats.append(f"&#128722; {product.clicks_count}")
        if stats:
            text += f"&#128202; {' | '.join(stats)}"

        keyboard = [
            [InlineKeyboardButton("&#128722; Купить товар", callback_data=f"buy_{product.id}")],
            [
                InlineKeyboardButton("&#128281; Назад", callback_data="catalog_0"),
                InlineKeyboardButton("&#127968; Главная", callback_data="start"),
            ],
        ]
        query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

    # ---------- Остальные команды ----------
    def search_help(self, update: Update, context):
        """Справка по поиску"""
        text = (
            "&#128269; <b>Как искать товары:</b>\n\n"
            "&#128161; <b>Просто напишите:</b>\n"
            "• Название товара: <i>мёд</i>, <i>прополис</i>\n"
            "• Тип продукта: <i>крем</i>, <i>драже</i>\n"
            "• Назначение: <i>для иммунитета</i>, <i>от простуды</i>\n\n"
            "&#127919; <b>Популярные запросы:</b>\n"
            "• Мёд алтайский\n"
            "• Прополис водный\n"
            "• Крем для лица\n"
            "• Драже иммунитет\n"
            "• Пыльца пчелиная\n\n"
            "&#9889; Поиск работает умно — находит товары даже при неточном написании!"
        )
        keyboard = [
            [
                InlineKeyboardButton("&#128218; Категории", callback_data="categories_0"),
                InlineKeyboardButton("&#128293; Хиты", callback_data="hits_0"),
            ],
            [InlineKeyboardButton("&#127968; Главная", callback_data="start")],
        ]
        self._send_or_edit_message(update, text, InlineKeyboardMarkup(keyboard))

    def contact(self, update: Update, context):
        """Контактная информация"""
        text = (
            "&#128222; <b>Контакты ТенториумРБ</b>\n\n"
            "<b>Для заказов и консультаций:</b>\n\n"
            "&#128241; <b>Телефон:</b> +7 (927) 338-54-08\n"
            "&#128231; <b>Email:</b> info@tentoriumrb.ru\n"
            "&#128172; <b>WhatsApp:</b> +7 (927) 338-54-08\n"
            "&#129302; <b>Telegram:</b> @Tent2024Bot\n\n"
            "&#127760; <b>Сайт:</b> https://tentoriumrb.ru\n\n"
            "&#128338; <b>Время работы бота:</b> 24/7\n"
            "&#128104;&#8205;&#128188; <b>Менеджер:</b> Пн-Пт 9:00-18:00\n\n"
            "&#128666; <b>Доставка:</b> Россия, Казахстан, Беларусь"
        )
        keyboard = [[InlineKeyboardButton("&#127968; Главная", callback_data="start")]]
        self._send_or_edit_message(update, text, InlineKeyboardMarkup(keyboard))

    def about(self, update: Update, context):
        """О компании"""
        text = (
            "&#127970; <b>О компании Тенториум</b>\n\n"
            "&#127855; <b>Тенториум</b> — ведущий российский производитель продуктов пчеловодства "
            "и натуральной косметики с 30-летней историей.\n\n"
            "&#11088; <b>Наши преимущества:</b>\n"
            "• Собственная сырьевая база\n"
            "• Контроль качества на всех этапах\n"
            "• Экологически чистые продукты\n"
            "• Научные исследования\n"
            "• Международные сертификаты\n\n"
            "&#127775; <b>Продукция:</b>\n"
            "• Мёд разных сортов\n"
            "• Прополис и продукты с прополисом\n"
            "• Перга, пыльца, маточное молочко\n"
            "• Натуральная косметика\n"
            "• БАД и драже\n\n"
            "&#9989; Вся продукция сертифицирована"
        )
        keyboard = [
            [
                InlineKeyboardButton("&#128203; Каталог", callback_data="catalog_0"),
                InlineKeyboardButton("&#128222; Контакты", callback_data="contact"),
            ],
            [InlineKeyboardButton("&#127968; Главная", callback_data="start")],
        ]
        self._send_or_edit_message(update, text, InlineKeyboardMarkup(keyboard))

    def help_command(self, update: Update, context):
        """Справка по боту"""
        text = (
            "&#10067; <b>Справка по использованию бота</b>\n\n"
            "&#127919; <b>Команды:</b>\n"
            "/start — Главное меню\n"
            "/catalog — Каталог товаров\n"
            "/categories — Категории\n"
            "/bestsellers — Хиты продаж\n"
            "/new — Новинки\n"
            "/discounts — Скидки\n"
            "/search — Помощь по поиску\n"
            "/contact — Контакты\n"
            "/about — О компании\n\n"
            "&#128269; <b>Поиск:</b>\n"
            "Просто напишите название товара или что ищете\n\n"
            "&#128722; <b>Заказ:</b>\n"
            "Нажмите «Купить» &#8594; свяжитесь с нами для оформления\n\n"
            "&#128172; <b>Вопросы?</b> Обращайтесь в /contact"
        )
        keyboard = [
            [
                InlineKeyboardButton("&#128203; Каталог", callback_data="catalog_0"),
                InlineKeyboardButton("&#128269; Поиск", callback_data="search_help"),
            ],
            [InlineKeyboardButton("&#127968; Главная", callback_data="start")],
        ]
        self._send_or_edit_message(update, text, InlineKeyboardMarkup(keyboard))

    # ---------- Покупка товара ----------
    @db_safe
    def handle_buy_product(self, query, product_id: int):
        """Обработка покупки товара (редактирование сообщения)"""
        if not self.check_models():
            query.edit_message_text("&#9888;&#65039; Покупка временно недоступна.", parse_mode="HTML")
            return

        try:
            from content.models import Product, ProductClick, Lead, TelegramUser
            product = Product.objects.get(id=product_id, is_active=True)

        except Product.DoesNotExist:
            query.edit_message_text("&#10060; Товар не найден.", parse_mode="HTML")
            return
        except Exception as e:
            logger.error("Ошибка при покупке: %s", e)
            query.edit_message_text("&#9888;&#65039; Ошибка при оформлении заказа.", parse_mode="HTML")
            return

        user = query.from_user

        try:
            if hasattr(product, 'clicks_count'):
                product.clicks_count = (product.clicks_count or 0) + 1
                product.save(update_fields=['clicks_count'])

            try:
                ProductClick.objects.create(
                    product=product,
                    ip_address="127.0.0.1",
                    user_agent="Telegram Bot",
                    referrer="telegram",
                )
            except Exception:
                pass

            tg_user, _ = TelegramUser.objects.get_or_create(
                user_id=user.id,
                defaults={
                    'username': user.username or '',
                    'first_name': user.first_name or '',
                    'last_name': user.last_name or '',
                    'is_active': True,
                }
            )

            Lead.objects.create(
                name=f"{(user.first_name or '')} {(user.last_name or '')}".strip() or "Пользователь Telegram",
                phone=f"@{user.username}" if user.username else f"TG:{user.id}",
                email=f"telegram_user_{user.id}@telegram.local",
                message=f"Интерес к товару: {product.name} через Telegram бота",
                source="telegram",
                telegram_user=tg_user,
                product_interest=product,
            )
        except Exception as e:
            logger.error("Ошибка создания лида: %s", e)

        name = esc(product.name)
        price_text = self._format_price(product)
        referral_url = getattr(product, 'referral_url', None) or "https://tentoriumrb.ru/products/"

        text = (
            f"&#128722; <b>Заказ: {name}</b>\n\n"
            "&#128222; <b>Для оформления заказа свяжитесь с нами:</b>\n\n"
            "&#128241; <b>Телефон:</b> +7 (927) 338-54-08\n"
            "&#128231; <b>Email:</b> info@tentoriumrb.ru\n"
            "&#128172; <b>WhatsApp:</b> +7 (927) 338-54-08\n\n"
            "&#127760; <b>Или купите на сайте:</b>\n"
            f"{esc(referral_url)}\n\n"
            f"&#128176; <b>Цена:</b> {price_text}\n"
            f"&#128230; <b>Товар:</b> {name}\n\n"
            "&#128172; <b>При обращении укажите:</b>\n"
            f"«Заказ из Telegram: {name}»\n\n"
            "&#9989; Наш менеджер свяжется с вами в ближайшее время!\n\n"
            "&#128666; <b>Доставка:</b> Россия, Казахстан, Беларусь\n"
            "&#128179; <b>Оплата:</b> любым удобным способом"
        )

        keyboard = [
            [
                InlineKeyboardButton("&#128281; К товару", callback_data=f"product_{product_id}"),
                InlineKeyboardButton("&#128203; Каталог", callback_data="catalog_0"),
            ],
            [InlineKeyboardButton("&#127968; Главная", callback_data="start")],
        ]
        query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

    # ---------- Сохранение пользователя ----------
    @db_safe
    def save_telegram_user(self, user):
        """Сохранение пользователя Telegram"""
        if not self.check_models():
            return
        try:
            from content.models import TelegramUser

            if not user or not hasattr(user, 'id'):
                return

            tg_user, created = TelegramUser.objects.get_or_create(
                user_id=user.id,
                defaults={
                    'username': user.username or '',
                    'first_name': user.first_name or '',
                    'last_name': user.last_name or '',
                    'is_active': True,
                }
            )

            if not created:
                update_fields = []
                if tg_user.username != (user.username or ''):
                    tg_user.username = user.username or ''
                    update_fields.append('username')
                if tg_user.first_name != (user.first_name or ''):
                    tg_user.first_name = user.first_name or ''
                    update_fields.append('first_name')
                if tg_user.last_name != (user.last_name or ''):
                    tg_user.last_name = user.last_name or ''
                    update_fields.append('last_name')
                if update_fields:
                    tg_user.save(update_fields=update_fields)

        except Exception as e:
            logger.error("Ошибка сохранения пользователя Telegram: %s", e)

    # ---------- Запуск бота ----------
    def run(self):
        """Запуск бота"""
        logger.info("Запуск улучшенного Telegram бота Тенториум...")
        try:
            self.updater.start_polling()
            logger.info("Бот успешно запущен и готов к работе!")
            # бесконечный цикл (можно заменить на self.updater.idle())
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Остановка бота по команде пользователя...")
            self.updater.stop()
            logger.info("Бот остановлен.")
        except Exception as e:
            logger.error("Ошибка запуска бота: %s", e)
            self.updater.stop()
            raise


# ---------- Django Command ----------
class Command(BaseCommand):
    help = "Запуск улучшенного Telegram бота Тенториум"

    def add_arguments(self, parser):
        parser.add_argument(
            "--test",
            action="store_true",
            help="Тестовый режим (только проверка подключения)",
        )
        parser.add_argument(
            "--debug",
            action="store_true",
            help="Включить режим отладки",
        )

    def handle(self, *args, **options):
        try:
            if options.get("debug"):
                logging.getLogger().setLevel(logging.DEBUG)

            if options.get("test"):
                self.stdout.write("&#129514; Тестирование подключения к Telegram...")
                try:
                    from telegram import Bot
                    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
                    me = bot.get_me()
                    self.stdout.write(
                        self.style.SUCCESS(f"&#9989; Подключение успешно! Бот: @{me.username} ({me.first_name})")
                    )
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"&#10060; Ошибка подключения: {e}"))
                return

            if not settings.configured:
                self.stdout.write(self.style.ERROR("&#10060; Django не настроен."))
                return

            if not getattr(settings, "TELEGRAM_BOT_TOKEN", None):
                self.stdout.write(self.style.ERROR("&#10060; TELEGRAM_BOT_TOKEN не найден в настройках."))
                return

            bot = ImprovedTelegramBot()
            self.stdout.write(self.style.SUCCESS("&#128640; Запуск улучшенного бота Тенториум..."))
            bot.run()

        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("&#9209;&#65039; Бот остановлен пользователем"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"&#10060; Критическая ошибка: {str(e)}"))
            if options.get("debug"):
                import traceback
                self.stdout.write(traceback.format_exc())
            raise CommandError(str(e))
