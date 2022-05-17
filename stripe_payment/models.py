from django.utils.translation import ugettext_lazy as _

from django.db import models
from stripe_payment.utils import *
from stripe.error import StripeError

from django.contrib.auth.models import User
from django.contrib.auth import get_user_model
User = get_user_model()


class PaymentMethod(models.Model):
    user = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='payment_method')
    customer = models.ForeignKey('stripe_payment.StripePayment', on_delete=models.SET_NULL,
                                 null=True, blank=True, related_name='payment_method')

    token_id = models.CharField(_('Token ID'), max_length=255, unique=True, blank=True, null=True)
    payment_method_id = models.CharField(_('Payment method id'), max_length=120, blank=True, null=True)
    fingerprint = models.CharField(_('Fingerprint'), max_length=120, blank=True, null=True)

    DEFAULT_CHOICES = (
        ('0', 'no'),
        ('1', 'yes')
    )
    STATUS_CHOICES = (
        ('0', 'inactive'),
        ('1', 'active')
    )
    is_default = models.CharField(max_length=2, choices=DEFAULT_CHOICES, default=0)
    status = models.CharField(max_length=2, choices=STATUS_CHOICES, default=1)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return str(self.payment_method_id)

    class Meta:
        verbose_name = _('Payment Method')
        verbose_name_plural = _('Payment Methods')
        ordering = ['-id']

    def api_details(self):
        try:
            from django.conf import settings
            pricing_plan = retrieve_pricing_plan(settings.STRIPE_ANNUAL_PRICE_PLAN_ID)
            product = retrieve_stripe_product(pricing_plan.product)
            payment_method = retrieve_payment_method(self.payment_method_id)
            subscription_id = self.customer.subscription_id
            return {
                'payment_method': payment_method,
                'product': {
                    'product_id': product.id,
                    'product_name': product.name,
                    'product_description': product.description,
                    'product_image': product.images,
                    'product_price_id': pricing_plan.id,
                    'currency': pricing_plan.currency,
                    'amount': int(pricing_plan.unit_amount/100),
                    'billing_scheme': pricing_plan.billing_scheme,
                    'recurring': pricing_plan.recurring,
                },
                'subscription': {
                    'subscription_id': subscription_id,
                    'is_cancel': self.customer.is_cancel
                }
            }
        except StripeError as e:
            print(_(e.user_message + '[SP-175]'))
        except Exception as e:
            print(e + '[SP-176]')


class StripePayment(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='stripe_payment')

    customer_id = models.CharField(_('Customer id'), max_length=200)
    payment_method_id = models.CharField(_('Payment Method id'), max_length=200, null=True, blank=True)
    subscription_id = models.CharField(_('Subscription id'), max_length=200, null=True, blank=True)

    paid_until = models.CharField( _("Paid until"), max_length=200, null=True, blank=True)
    no_of_subscriptions = models.IntegerField(_("No of subscription"), default=0)

    STATUS_CHOICES = (
        ('-1', 'incomplete'),
        ('0', 'inactive'),
        ('1', 'active')
    )
    CANCEL = (
        ('0', 'no'),
        ('1', 'yes')
    )
    status = models.CharField(max_length=2, choices=STATUS_CHOICES, default='-1')
    is_cancel = models.CharField(max_length=2, choices=CANCEL, default='0')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return str(self.customer_id)

    class Meta:
        verbose_name = _('Stripe Payment')
        verbose_name_plural = _('Stripe Payments')
        ordering = ['-id']
