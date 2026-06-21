from django.urls import path
from . import views

urlpatterns = [
    path('process-payment/', views.process_payment),
    path('users/', views.create_user),
    path('users/<int:user_id>/', views.get_user),
]
