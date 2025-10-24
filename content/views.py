# content/views.py
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q, Count, Avg
from .models import (
    Product, ProductCategory, ProductView, ProductClick, SiteVisit, 
    ProductReview, Banner, SiteSettings, Article, BlogPost, Comment, Lead
)
from .forms import CommentForm, CustomUserCreationForm

def get_client_ip(request):
    """Получение IP адреса клиента"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def track_visit(request, page_url):
    """Отслеживание посещений страниц"""
    try:
        SiteVisit.objects.create(
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            page_url=page_url,
            referrer=request.META.get('HTTP_REFERER', ''),
            session_id=request.session.session_key or ''
        )
    except:
        pass  # Игнорируем ошибки аналитики

def homepage(request):
    """Главная страница с продуктами"""
    track_visit(request, request.build_absolute_uri())
    
    # Получаем настройки сайта
    site_settings = SiteSettings.objects.first()
    
    # Получаем баннеры
    banners = Banner.objects.filter(is_active=True).order_by('order')[:3]
    
    # Рекомендуемые продукты
    featured_products = Product.objects.filter(
        is_active=True, is_featured=True
    ).order_by('order')[:6]
    
    # Хиты продаж
    bestseller_products = Product.objects.filter(
        is_active=True, is_bestseller=True
    ).order_by('order')[:6]
    
    # Новинки
    new_products = Product.objects.filter(
        is_active=True, is_new=True
    ).order_by('-created_at')[:6]
    
    # Все категории с количеством товаров
    categories = ProductCategory.objects.filter(
        is_active=True
    ).annotate(products_count=Count('products')).order_by('order')
    
    context = {
        'site_settings': site_settings,
        'banners': banners,
        'featured_products': featured_products,
        'bestseller_products': bestseller_products,
        'new_products': new_products,
        'categories': categories,
    }
    
    return render(request, 'content/homepage_new.html', context)

def products_list(request):
    """Каталог всех продуктов"""
    track_visit(request, request.build_absolute_uri())
    
    # Фильтрация
    category_id = request.GET.get('category')
    search_query = request.GET.get('search', '')
    sort_by = request.GET.get('sort', 'order')
    
    products = Product.objects.filter(is_active=True)
    
    if category_id:
        products = products.filter(category_id=category_id)
    
    if search_query:
        products = products.filter(
            Q(name__icontains=search_query) |
            Q(short_description__icontains=search_query) |
            Q(composition__icontains=search_query)
        )
    
    # Сортировка
    if sort_by == 'price_asc':
        products = products.order_by('price')
    elif sort_by == 'price_desc':
        products = products.order_by('-price')
    elif sort_by == 'name':
        products = products.order_by('name')
    elif sort_by == 'newest':
        products = products.order_by('-created_at')
    else:
        products = products.order_by('order', '-created_at')
    
    categories = ProductCategory.objects.filter(is_active=True).order_by('order')
    
    context = {
        'products': products,
        'categories': categories,
        'current_category': category_id,
        'search_query': search_query,
        'sort_by': sort_by,
    }
    
    return render(request, 'content/products_list.html', context)

def product_detail(request, pk):
    """Детальная страница продукта"""
    product = get_object_or_404(Product, pk=pk, is_active=True)
    
    # Отслеживание просмотра
    track_visit(request, request.build_absolute_uri())
    
    # Увеличиваем счетчик просмотров
    product.views_count += 1
    product.save(update_fields=['views_count'])
    
    # Записываем в аналитику просмотров
    try:
        ProductView.objects.create(
            product=product,
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            referrer=request.META.get('HTTP_REFERER', '')
        )
    except:
        pass
    
    # Получаем отзывы
    reviews = ProductReview.objects.filter(
        product=product, is_active=True
    ).order_by('-created_at')
    
    # Средний рейтинг
    avg_rating = reviews.aggregate(avg=Avg('rating'))['avg'] or 0
    
    # Рекомендуемые товары из той же категории
    related_products = Product.objects.filter(
        category=product.category, is_active=True
    ).exclude(pk=product.pk).order_by('?')[:4]
    
    context = {
        'product': product,
        'reviews': reviews,
        'avg_rating': round(avg_rating, 1),
        'related_products': related_products,
    }
    
    return render(request, 'content/product_detail.html', context)

@csrf_exempt
def product_click(request, pk):
    """Обработка клика по реферальной ссылке"""
    if request.method == 'POST':
        product = get_object_or_404(Product, pk=pk, is_active=True)
        
        # Увеличиваем счетчик кликов
        product.clicks_count += 1
        product.save(update_fields=['clicks_count'])
        
        # Записываем в аналитику кликов
        try:
            ProductClick.objects.create(
                product=product,
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                referrer=request.META.get('HTTP_REFERER', '')
            )
        except:
            pass
        
        return JsonResponse({
            'success': True,
            'redirect_url': product.referral_url
        })
    
    return JsonResponse({'success': False})

def category_products(request, category_id):
    """Продукты определенной категории"""
    category = get_object_or_404(ProductCategory, pk=category_id, is_active=True)
    
    track_visit(request, request.build_absolute_uri())
    
    products = Product.objects.filter(
        category=category, is_active=True
    ).order_by('order', '-created_at')
    
    context = {
        'category': category,
        'products': products,
    }
    
    return render(request, 'content/category_products.html', context)

def search_products(request):
    """Поиск продуктов"""
    query = request.GET.get('q', '')
    
    if query:
        products = Product.objects.filter(
            Q(name__icontains=query) |
            Q(short_description__icontains=query) |
            Q(composition__icontains=query) |
            Q(benefits__icontains=query),
            is_active=True
        ).order_by('-views_count')
    else:
        products = Product.objects.none()
    
    context = {
        'products': products,
        'query': query,
    }
    
    return render(request, 'content/search_results.html', context)

# ===== СТАРЫЕ ПРЕДСТАВЛЕНИЯ (для совместимости) =====

def article_list(request):
    articles = Article.objects.all().order_by('-created_at')
    return render(request, 'content/article_list.html', {'articles': articles})

def article_detail(request, pk):
    article = get_object_or_404(Article, pk=pk)
    article.views += 1
    article.save(update_fields=['views'])
    return render(request, 'content/article_detail.html', {'article': article})

def blog_list(request):
    posts = BlogPost.objects.all().order_by('-created_at')
    return render(request, 'content/blog_list.html', {'posts': posts})

def blog_detail(request, pk):
    post = get_object_or_404(BlogPost, pk=pk)
    post.views += 1
    post.save(update_fields=['views'])

    comments = post.comments.filter(is_approved=True)
    if request.method == "POST":
        if request.user.is_authenticated:
            form = CommentForm(request.POST)
            if form.is_valid():
                comment = form.save(commit=False)
                comment.post = post
                comment.user = request.user
                comment.save()
                return redirect('blog_detail', pk=post.pk)
        else:
            form = CommentForm()
            return redirect('/admin/login/?next=/blog/%d/' % post.pk)
    else:
        form = CommentForm()
    return render(request, 'content/blog_detail.html', {
        'post': post,
        'comments': comments,
        'form': form,
    })

@login_required
def partner_cabinet(request):
    profile = getattr(request.user, 'partner_profile', None)
    if profile is None:
        return HttpResponse("Профиль не найден, обратитесь к администратору.", status=500)
    return render(request, 'content/partner_cabinet.html', {'profile': profile})
  
def register_view(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Регистрация прошла успешно. Теперь вы можете войти.')
            return redirect('login')
    else:
        form = CustomUserCreationForm()
    return render(request, 'registration/register.html', {'form': form})  
  
def privacy_policy(request):
    from django.utils import timezone
    return render(request, 'content/privacy_policy.html', {
        'current_date': timezone.now()
    })

def terms_conditions(request):
    from django.utils import timezone
    return render(request, 'content/terms_conditions.html', {
        'current_date': timezone.now()
    })
  