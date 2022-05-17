from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()

router.register('payment-method', views.PaymentMethodView,basename='payment_method')
router.register('payment', views.StripePaymentView,basename='payment')

urlpatterns = [
    path('config/', views.Config.as_view()),
    path('stripe-webhooks/', views.stripe_webhooks, name='stripe_webhooks'),
    path('', include(router.urls)),
]
