# content/admin.py
from django.contrib import admin
from django.db.models import Count, Sum
from django.utils.html import format_html
from django.urls import path
from django.template.response import TemplateResponse
from django.utils import timezone
from datetime import datetime, timedelta
from .models import (
    ProductCategory, Product, ProductView, ProductClick, SiteVisit, 
    ProductReview, Banner, SiteSettings, TelegramUser, TelegramMessage,
    Lead, Category, Article, BlogPost, Comment, PartnerProfile
)

# ===== ПРОДУКТЫ И КАТЕГОРИИ =====

@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'order', 'products_count')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'description')
    ordering = ('order', 'name')
    
    def products_count(self, obj):
        return obj.products.count()
    products_count.short_description = 'Количество продуктов'

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price', 'is_active', 'is_featured', 
                    'views_count', 'clicks_count', 'conversion_rate', 'created_at')
    list_filter = ('category', 'is_active', 'is_featured', 'is_bestseller', 'is_new', 'created_at')
    search_fields = ('name', 'short_description', 'composition')
    ordering = ('order', '-created_at')
    readonly_fields = ('views_count', 'clicks_count', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'category', 'short_description', 'full_description', 'image')
        }),
        ('Цены и характеристики', {
            'fields': ('price', 'old_price', 'weight', 'composition', 'benefits')
        }),
        ('Реферальная ссылка', {
            'fields': ('referral_url',)
        }),
        ('Настройки отображения', {
            'fields': ('is_active', 'is_featured', 'is_bestseller', 'is_new', 'order')
        }),
        ('Статистика', {
            'fields': ('views_count', 'clicks_count', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def conversion_rate(self, obj):
        if obj.views_count > 0:
            rate = (obj.clicks_count / obj.views_count) * 100
            return f"{rate:.2f}%"
        return "0%"
    conversion_rate.short_description = 'Конверсия'

# ===== TELEGRAM BOT =====

@admin.register(TelegramUser)
class TelegramUserAdmin(admin.ModelAdmin):
    list_display = ('user_id', 'full_name', 'username', 'is_active', 'messages_count', 'orders_count', 'last_activity')
    list_filter = ('is_active', 'is_blocked', 'created_at', 'last_activity')
    search_fields = ('username', 'first_name', 'last_name', 'user_id')
    readonly_fields = ('user_id', 'created_at', 'last_activity', 'messages_count')
    ordering = ('-last_activity',)
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('user_id', 'username', 'first_name', 'last_name')
        }),
        ('Контакты', {
            'fields': ('phone', 'city')
        }),
        ('Статус', {
            'fields': ('is_active', 'is_blocked')
        }),
        ('Статистика', {
            'fields': ('messages_count', 'orders_count', 'created_at', 'last_activity'),
            'classes': ('collapse',)
        }),
    )

@admin.register(TelegramMessage)
class TelegramMessageAdmin(admin.ModelAdmin):
    list_display = ('telegram_user', 'message_type', 'text_preview', 'is_command', 'command_name', 'created_at')
    list_filter = ('message_type', 'is_command', 'created_at')
    search_fields = ('telegram_user__username', 'telegram_user__first_name', 'text', 'command_name')
    readonly_fields = ('telegram_user', 'message_id', 'message_type', 'text', 'created_at', 'is_command', 'command_name')
    ordering = ('-created_at',)
    
    def text_preview(self, obj):
        return obj.text[:50] + '...' if len(obj.text) > 50 else obj.text
    text_preview.short_description = 'Текст сообщения'
    
    def has_add_permission(self, request):
        return False

# ===== АНАЛИТИКА =====

@admin.register(ProductView)
class ProductViewAdmin(admin.ModelAdmin):
    list_display = ('product', 'ip_address', 'telegram_user', 'created_at')
    list_filter = ('created_at', 'product__category')
    search_fields = ('product__name', 'ip_address')
    readonly_fields = ('product', 'ip_address', 'user_agent', 'referrer', 'telegram_user', 'created_at')
    ordering = ('-created_at',)
    
    def has_add_permission(self, request):
        return False

@admin.register(ProductClick)
class ProductClickAdmin(admin.ModelAdmin):
    list_display = ('product', 'ip_address', 'telegram_user', 'created_at')
    list_filter = ('created_at', 'product__category')
    search_fields = ('product__name', 'ip_address')
    readonly_fields = ('product', 'ip_address', 'user_agent', 'referrer', 'telegram_user', 'created_at')
    ordering = ('-created_at',)
    
    def has_add_permission(self, request):
        return False

@admin.register(SiteVisit)
class SiteVisitAdmin(admin.ModelAdmin):
    list_display = ('page_url', 'ip_address', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('ip_address', 'page_url')
    readonly_fields = ('ip_address', 'user_agent', 'page_url', 'referrer', 'session_id', 'created_at')
    ordering = ('-created_at',)
    
    def has_add_permission(self, request):
        return False

# ===== ЛИДЫ И ЗАЯВКИ =====

@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'email', 'source', 'status', 'product_interest', 'created_at')
    list_filter = ('source', 'status', 'created_at')
    search_fields = ('name', 'phone', 'email', 'telegram_user__username')
    readonly_fields = ('created_at', 'telegram_user')
    
    fieldsets = (
        ('Контактная информация', {
            'fields': ('name', 'phone', 'email', 'message')
        }),
        ('Источник и интересы', {
            'fields': ('source', 'telegram_user', 'product_interest')
        }),
        ('Обработка', {
            'fields': ('status', 'notes', 'processed_at')
        }),
        ('Системная информация', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_contacted', 'mark_converted']
    
    def mark_contacted(self, request, queryset):
        queryset.update(status='contacted', processed_at=timezone.now())
        self.message_user(request, f"Отмечено как связались: {queryset.count()}")
    mark_contacted.short_description = "Отметить как связались"
    
    def mark_converted(self, request, queryset):
        queryset.update(status='converted', processed_at=timezone.now())
        self.message_user(request, f"Отмечено как конверсия: {queryset.count()}")
    mark_converted.short_description = "Отметить как конверсия"

# ===== КОНТЕНТ =====

@admin.register(ProductReview)
class ProductReviewAdmin(admin.ModelAdmin):
    list_display = ('product', 'author_name', 'rating', 'is_active', 'created_at')
    list_filter = ('rating', 'is_active', 'created_at')
    search_fields = ('author_name', 'text', 'product__name')
    ordering = ('-created_at',)

@admin.register(Banner)
class BannerAdmin(admin.ModelAdmin):
    list_display = ('title', 'is_active', 'order', 'created_at')
    list_filter = ('is_active', 'created_at')
    ordering = ('order',)

@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        return False

# ===== КАСТОМНАЯ АДМИН ПАНЕЛЬ С АНАЛИТИКОЙ =====

class CustomAdminSite(admin.AdminSite):
    site_header = "ТенториумРБ - Панель управления"
    site_title = "Админ панель"
    index_title = "Управление сайтом и Telegram ботом"
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('analytics/', self.admin_view(self.analytics_view), name='analytics'),
        ]
        return custom_urls + urls
    
    def analytics_view(self, request):
        # Получаем данные за последние 30 дней
        today = timezone.now().date()
        thirty_days_ago = today - timedelta(days=30)
        
        # Статистика по продуктам
        products_stats = Product.objects.filter(is_active=True).order_by('-views_count')[:10]
        
        # Общая статистика
        total_products = Product.objects.filter(is_active=True).count()
        total_visits = SiteVisit.objects.filter(created_at__date__gte=thirty_days_ago).count()
        total_product_views = ProductView.objects.filter(created_at__date__gte=thirty_days_ago).count()
        total_clicks = ProductClick.objects.filter(created_at__date__gte=thirty_days_ago).count()
        total_telegram_users = TelegramUser.objects.filter(is_active=True).count()
        total_leads = Lead.objects.filter(created_at__date__gte=thirty_days_ago).count()
        
        # Статистика по дням за последние 7 дней
        last_7_days = []
        for i in range(6, -1, -1):
            date = today - timedelta(days=i)
            visits = SiteVisit.objects.filter(created_at__date=date).count()
            views = ProductView.objects.filter(created_at__date=date).count()
            clicks = ProductClick.objects.filter(created_at__date=date).count()
            leads = Lead.objects.filter(created_at__date=date).count()
            last_7_days.append({
                'date': date,
                'visits': visits,
                'views': views,
                'clicks': clicks,
                'leads': leads
            })
        
        # Топ продукты по просмотрам
        top_viewed = Product.objects.filter(is_active=True).order_by('-views_count')[:5]
        
        # Топ продукты по кликам
        top_clicked = Product.objects.filter(is_active=True).order_by('-clicks_count')[:5]
        
        # Конверсия
        overall_conversion = (total_clicks / total_product_views * 100) if total_product_views > 0 else 0
        
        context = {
            'title': 'Аналитика ТенториумРБ',
            'total_products': total_products,
            'total_visits': total_visits,
            'total_product_views': total_product_views,
            'total_clicks': total_clicks,
            'total_telegram_users': total_telegram_users,
            'total_leads': total_leads,
            'last_7_days': last_7_days,
            'top_viewed': top_viewed,
            'top_clicked': top_clicked,
            'overall_conversion': round(overall_conversion, 2),
            'products_stats': products_stats,
        }
        
        return TemplateResponse(request, 'admin/analytics.html', context)

# ===== СТАРЫЕ МОДЕЛИ (для совместимости) =====

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)

@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'category', 'created_at', 'views')
    search_fields = ('title',)
    list_filter = ('category',)
    readonly_fields = ('created_at', 'views')

@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'author', 'category', 'created_at', 'views')
    search_fields = ('title', 'author__username')
    list_filter = ('category', 'author')
    readonly_fields = ('created_at', 'views')

@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('id', 'post', 'user', 'created_at', 'is_approved')
    search_fields = ('user__username', 'text')
    list_filter = ('is_approved',)
    readonly_fields = ('created_at',)
    actions = ['approve_comments']

    def approve_comments(self, request, queryset):
        queryset.update(is_approved=True)
    approve_comments.short_description = "Одобрить выбранные комментарии"

@admin.register(PartnerProfile)
class PartnerProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone', 'telegram', 'is_partner')
    search_fields = ('user__username', 'phone', 'telegram')
    