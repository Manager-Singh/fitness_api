from django.urls import path
from . import views

urlpatterns = [
    path('all', views.get_all_payment_packages),
    path('<int:package_id>', views.get_payment_package),
    path('create', views.create_payment_package),
    path('<int:package_id>/update', views.update_payment_package),
    path('<int:package_id>/delete', views.delete_payment_package),
]
