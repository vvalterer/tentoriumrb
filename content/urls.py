# content/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # Главная страница
    path('', views.homepage, name='homepage'),
    
    # Продукты
    path('products/', views.products_list, name='products_list'),
    path('product/<int:pk>/', views.product_detail, name='product_detail'),
    path('product/<int:pk>/click/', views.product_click, name='product_click'),
    path('category/<int:category_id>/', views.category_products, name='category_products'),
    path('search/', views.search_products, name='search_products'),
    
    # Старые страницы (для совместимости)
    path('articles/', views.article_list, name='article_list'),
    path('article/<int:pk>/', views.article_detail, name='article_detail'),
    path('blog/', views.blog_list, name='blog_list'),
    path('blog/<int:pk>/', views.blog_detail, name='blog_detail'),
    path('cabinet/', views.partner_cabinet, name='partner_cabinet'),
]
