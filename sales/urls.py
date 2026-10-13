from django.urls import path

from . import views

urlpatterns = [
    path('sales/api/customers/', views.customers_search, name='customers_search'),
    path('sales/api/customers/options/', views.customer_form_options, name='customer_form_options'),
    path('sales/api/customers/create/', views.customer_create, name='customer_create'),
    path('sales/api/carts/', views.carts_list, name='carts_list'),
    path('sales/api/carts/add/', views.cart_add, name='cart_add'),
    path('sales/api/carts/<int:cart_id>/remove/', views.cart_remove_item, name='cart_remove_item'),
    path('sales/api/carts/<int:cart_id>/clear/', views.cart_clear, name='cart_clear'),
    path('sales/api/carts/<int:cart_id>/close/', views.cart_close, name='cart_close'),
]
