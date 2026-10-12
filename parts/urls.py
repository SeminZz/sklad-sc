from django.urls import path

from . import views

urlpatterns = [
    path('sklad/', views.stock, name='stock'),
    path('sklad/api/parts/', views.stock_api, name='stock_api'),
    path('sklad/api/models/', views.models_api, name='models_api'),
]
