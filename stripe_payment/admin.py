from django.contrib import admin
from jmespath import search

from .models import StripePayment, PaymentMethod


@admin.register(StripePayment)
class StripePaymentAdmin(admin.ModelAdmin):
    list_display = ['user','customer_id','payment_method_id','subscription_id','paid_until','status','is_cancel','no_of_subscriptions']
    readonly_fields = ['user','customer_id','payment_method_id','subscription_id','paid_until','status','is_cancel','no_of_subscriptions']
    search_fields = ['customer_id']


@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ['user','customer','token_id','payment_method_id','fingerprint','is_default','status']
    readonly_fields = ['user','customer','token_id','payment_method_id','fingerprint','is_default','status']
    search_fields = ['payment_method_id']

