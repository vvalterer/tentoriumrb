# content/models.py
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

# ===== ОСНОВНЫЕ МОДЕЛИ ПРОДУКТОВ =====

# Категория продуктов
class ProductCategory(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name='Название категории')
    description = models.TextField(blank=True, verbose_name='Описание категории')
    image = models.ImageField(upload_to='categories/', blank=True, verbose_name='Изображение категории')
    order = models.PositiveIntegerField(default=0, verbose_name='Порядок сортировки')
    is_active = models.BooleanField(default=True, verbose_name='Активна')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Категория продукта"
        verbose_name_plural = "Категории продуктов"
        ordering = ['order', 'name']

# Продукт
class Product(models.Model):
    category = models.ForeignKey(ProductCategory, on_delete=models.CASCADE, related_name='products', verbose_name='Категория')
    name = models.CharField(max_length=200, verbose_name='Название продукта')
    short_description = models.CharField(max_length=300, verbose_name='Краткое описание')
    full_description = models.TextField(verbose_name='Полное описание')
    image = models.ImageField(upload_to='products/', verbose_name='Основное изображение')
    
    # Цены и характеристики
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Цена')
    old_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, verbose_name='Старая цена')
    weight = models.CharField(max_length=50, blank=True, verbose_name='Вес/объем')
    composition = models.TextField(blank=True, verbose_name='Состав')
    benefits = models.TextField(blank=True, verbose_name='Полезные свойства')
    
    # Реферальная ссылка и отслеживание
    referral_url = models.URLField(verbose_name='Реферальная ссылка')
    is_featured = models.BooleanField(default=False, verbose_name='Рекомендуемый товар')
    is_bestseller = models.BooleanField(default=False, verbose_name='Хит продаж')
    is_new = models.BooleanField(default=False, verbose_name='Новинка')
    is_active = models.BooleanField(default=True, verbose_name='Активен')
    
    # Статистика
    views_count = models.PositiveIntegerField(default=0, verbose_name='Просмотры')
    clicks_count = models.PositiveIntegerField(default=0, verbose_name='Клики по реферальной ссылке')
    
    # Служебные поля
    order = models.PositiveIntegerField(default=0, verbose_name='Порядок сортировки')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    def get_discount_percent(self):
        if self.old_price and self.old_price > self.price:
            return int(((self.old_price - self.price) / self.old_price) * 100)
        return 0

    class Meta:
        verbose_name = "Продукт"
        verbose_name_plural = "Продукты"
        ordering = ['order', '-created_at']

# ===== TELEGRAM BOT МОДЕЛИ =====

# Пользователи Telegram
class TelegramUser(models.Model):
    user_id = models.BigIntegerField(unique=True, verbose_name='Telegram ID')
    username = models.CharField(max_length=100, blank=True, null=True, verbose_name='Username')
    first_name = models.CharField(max_length=100, verbose_name='Имя')
    last_name = models.CharField(max_length=100, blank=True, verbose_name='Фамилия')
    is_active = models.BooleanField(default=True, verbose_name='Активен')
    is_blocked = models.BooleanField(default=False, verbose_name='Заблокирован')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата регистрации')
    last_activity = models.DateTimeField(auto_now=True, verbose_name='Последняя активность')
    
    # Дополнительная информация
    phone = models.CharField(max_length=20, blank=True, verbose_name='Телефон')
    city = models.CharField(max_length=100, blank=True, verbose_name='Город')
    
    # Статистика
    messages_count = models.PositiveIntegerField(default=0, verbose_name='Количество сообщений')
    orders_count = models.PositiveIntegerField(default=0, verbose_name='Количество заказов')

    def __str__(self):
        return f"@{self.username or self.user_id} - {self.first_name}"
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    class Meta:
        verbose_name = "Пользователь Telegram"
        verbose_name_plural = "Пользователи Telegram"
        ordering = ['-last_activity']

# Сообщения от пользователей Telegram
class TelegramMessage(models.Model):
    MESSAGE_TYPES = [
        ('text', 'Текст'),
        ('photo', 'Фото'),
        ('document', 'Документ'),
        ('contact', 'Контакт'),
        ('location', 'Геолокация'),
    ]
    
    telegram_user = models.ForeignKey(TelegramUser, on_delete=models.CASCADE, related_name='messages')
    message_id = models.BigIntegerField(verbose_name='ID сообщения')
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPES, default='text')
    text = models.TextField(blank=True, verbose_name='Текст сообщения')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата получения')
    
    # Для аналитики
    is_command = models.BooleanField(default=False, verbose_name='Команда')
    command_name = models.CharField(max_length=50, blank=True, verbose_name='Название команды')
    
    def __str__(self):
        return f"{self.telegram_user.first_name}: {self.text[:50]}"

    class Meta:
        verbose_name = "Сообщение Telegram"
        verbose_name_plural = "Сообщения Telegram"
        ordering = ['-created_at']

# ===== АНАЛИТИКА =====

# Аналитика просмотров продуктов
class ProductView(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='product_views')
    ip_address = models.GenericIPAddressField(verbose_name='IP адрес')
    user_agent = models.TextField(verbose_name='User Agent')
    referrer = models.URLField(blank=True, verbose_name='Источник перехода')
    telegram_user = models.ForeignKey(TelegramUser, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Пользователь Telegram')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Просмотр продукта"
        verbose_name_plural = "Просмотры продуктов"

# Аналитика кликов по реферальным ссылкам
class ProductClick(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='product_clicks')
    ip_address = models.GenericIPAddressField(verbose_name='IP адрес')
    user_agent = models.TextField(verbose_name='User Agent')
    referrer = models.URLField(blank=True, verbose_name='Источник перехода')
    telegram_user = models.ForeignKey(TelegramUser, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Пользователь Telegram')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Клик по продукту"
        verbose_name_plural = "Клики по продуктам"

# Общая аналитика сайта
class SiteVisit(models.Model):
    ip_address = models.GenericIPAddressField(verbose_name='IP адрес')
    user_agent = models.TextField(verbose_name='User Agent')
    page_url = models.URLField(verbose_name='Страница')
    referrer = models.URLField(blank=True, verbose_name='Источник перехода')
    session_id = models.CharField(max_length=100, blank=True, verbose_name='ID сессии')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Посещение сайта"
        verbose_name_plural = "Посещения сайта"

# ===== ЛИДЫ И ЗАЯВКИ =====

class Lead(models.Model):
    SOURCE_CHOICES = [
        ('website', 'Сайт'),
        ('telegram', 'Telegram'),
        ('whatsapp', 'WhatsApp'),
        ('phone', 'Телефон'),
        ('email', 'Email'),
        ('other', 'Другое'),
    ]
    
    STATUS_CHOICES = [
        ('new', 'Новый'),
        ('contacted', 'Связались'),
        ('converted', 'Конверсия'),
        ('rejected', 'Отказ'),
    ]
    
    name = models.CharField(max_length=100, verbose_name='Имя')
    phone = models.CharField(max_length=20, verbose_name='Телефон')
    email = models.EmailField(verbose_name='Email')
    message = models.TextField(blank=True, verbose_name='Сообщение')
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='website', verbose_name='Источник')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new', verbose_name='Статус')
    
    # Связи
    telegram_user = models.ForeignKey(TelegramUser, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Пользователь Telegram')
    product_interest = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Интерес к товару')
    
    # Временные метки
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата заявки')
    processed_at = models.DateTimeField(blank=True, null=True, verbose_name='Дата обработки')
    notes = models.TextField(blank=True, verbose_name='Заметки менеджера')

    def __str__(self):
        return f"{self.name} ({self.phone})"

    class Meta:
        verbose_name = "Лид"
        verbose_name_plural = "Лиды"
        ordering = ['-created_at']

# ===== КОНТЕНТ =====

# Отзывы о продуктах
class ProductReview(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    author_name = models.CharField(max_length=100, verbose_name='Имя автора')
    rating = models.PositiveIntegerField(choices=[(i, i) for i in range(1, 6)], verbose_name='Оценка')
    text = models.TextField(verbose_name='Текст отзыва')
    is_active = models.BooleanField(default=True, verbose_name='Активен')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Отзыв от {self.author_name} на {self.product.name}'

    class Meta:
        verbose_name = "Отзыв"
        verbose_name_plural = "Отзывы"
        ordering = ['-created_at']

# Баннеры для главной страницы
class Banner(models.Model):
    title = models.CharField(max_length=200, verbose_name='Заголовок')
    subtitle = models.CharField(max_length=300, blank=True, verbose_name='Подзаголовок')
    image = models.ImageField(upload_to='banners/', verbose_name='Изображение')
    link_text = models.CharField(max_length=100, blank=True, verbose_name='Текст кнопки')
    link_url = models.URLField(blank=True, verbose_name='Ссылка')
    is_active = models.BooleanField(default=True, verbose_name='Активен')
    order = models.PositiveIntegerField(default=0, verbose_name='Порядок')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "Баннер"
        verbose_name_plural = "Баннеры"
        ordering = ['order']

# Настройки сайта
class SiteSettings(models.Model):
    site_title = models.CharField(max_length=200, default='ТенториумРБ', verbose_name='Название сайта')
    site_description = models.TextField(verbose_name='Описание сайта')
    contact_phone = models.CharField(max_length=20, blank=True, verbose_name='Контактный телефон')
    contact_email = models.EmailField(blank=True, verbose_name='Контактный email')
    telegram_link = models.URLField(blank=True, verbose_name='Ссылка на Telegram')
    whatsapp_link = models.URLField(blank=True, verbose_name='Ссылка на WhatsApp')
    
    # SEO
    meta_keywords = models.TextField(blank=True, verbose_name='Ключевые слова')
    meta_description = models.TextField(blank=True, verbose_name='Мета описание')

    def __str__(self):
        return 'Настройки сайта'

    class Meta:
        verbose_name = "Настройки сайта"
        verbose_name_plural = "Настройки сайта"

# ===== СТАРЫЕ МОДЕЛИ (для совместимости) =====

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name='Название категории')

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Категория (старая)"
        verbose_name_plural = "Категории (старые)"
        
class Article(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='articles', verbose_name='Категория')
    title = models.CharField(max_length=200, verbose_name='Заголовок')
    content = models.TextField(verbose_name='Текст статьи')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата публикации')
    views = models.PositiveIntegerField(default=0, verbose_name='Количество просмотров')

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "Статья"
        verbose_name_plural = "Статьи"
        
class BlogPost(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='posts', verbose_name='Категория')
    author = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='Автор')
    title = models.CharField(max_length=200, verbose_name='Заголовок')
    content = models.TextField(verbose_name='Текст поста')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата публикации')
    views = models.PositiveIntegerField(default=0, verbose_name='Количество просмотров')

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "Блог-пост"
        verbose_name_plural = "Блог-посты"
        
class Comment(models.Model):
    post = models.ForeignKey(BlogPost, on_delete=models.CASCADE, related_name='comments', verbose_name='Пост')
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='Пользователь')
    text = models.TextField(verbose_name='Комментарий')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    is_approved = models.BooleanField(default=False, verbose_name='Одобрен модератором')

    def __str__(self):
        return f'Комментарий от {self.user.username}'

    class Meta:
        verbose_name = "Комментарий"
        verbose_name_plural = "Комментарии"
        
class PartnerProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='partner_profile')
    phone = models.CharField(max_length=20, verbose_name='Телефон', blank=True)
    telegram = models.CharField(max_length=50, verbose_name='Telegram', blank=True)
    is_partner = models.BooleanField(default=False, verbose_name='Партнёр')

    def __str__(self):
        return f"Профиль партнёра: {self.user.username}"
      
    class Meta:
        verbose_name = "Партнёр"
        verbose_name_plural = "Партнёры"
        
@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        PartnerProfile.objects.create(user=instance)
    else:
        if hasattr(instance, 'partner_profile'):
            instance.partner_profile.save()
            