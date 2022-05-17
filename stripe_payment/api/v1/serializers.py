from rest_framework import serializers
from django.utils.translation import ugettext_lazy as _
from stripe.error import StripeError

from stripe_payment.models import *
from stripe_payment.utils import *


class PaymentMethodSerializer(serializers.ModelSerializer):
    number = serializers.CharField(write_only=True, required=True)
    exp_month = serializers.IntegerField(write_only=True, required=True)
    exp_year = serializers.IntegerField(write_only=True, required=True)
    cvc = serializers.IntegerField(write_only=True, required=True)

    class Meta:
        model = PaymentMethod
        fields = ['number','exp_month','exp_year','cvc','user','customer','payment_method_id','is_default']

        extra_kwargs = {
                'user': {
                    'read_only': True
                },
                'customer': {
                    'read_only': True
                },
                'payment_method_id': {
                    'read_only': True
                },
                'is_default': {
                    'read_only': True
                }
            }

    def create(self, validated_data):
        request_user = self.context['request'].user
        data = validated_data

        try:
            customer = request_user.stripe_payment
        except Exception as e:
            customer = app_create_stripe_customer(request_user)
        if not customer:
            raise serializers.ValidationError({'error': _('Payment method create failed for this customer.[SP-101]')})

        try:
            card_token = create_card_token(data)
        except StripeError as e:
            raise serializers.ValidationError({'error': _(e.user_message + '[SP-102]')})

        check_exists = PaymentMethod.objects.filter(customer=customer, fingerprint=card_token.card.fingerprint)
        if check_exists.exists():
            raise serializers.ValidationError({'error': _('You already have this card saved.[SP-103]')})

        try:
            payment_method = create_payment_method(data, request_user)
            attach_payment_method(payment_method.id, customer.customer_id)
        except StripeError as e:
            raise serializers.ValidationError({'error': _(e.user_message + '[SP-104]')})
        except Exception as e:
            raise serializers.ValidationError({'error': _('Failed to create payment method.[SP-105]')})
        return PaymentMethod.objects.create(user=request_user,
                                            customer=request_user.stripe_payment,
                                            token_id=card_token.id,
                                            payment_method_id=payment_method.id,
                                            fingerprint=card_token.card.fingerprint,
                                            is_default=0)
        

class PaymentMethodDetailsSerializer(serializers.ModelSerializer):
    api_details = serializers.JSONField(read_only=True)

    class Meta:
        model = PaymentMethod
        fields = ['id', 'user', 'customer', 'payment_method_id','is_default', 'created_at', 'api_details']


class PaymentMethodUpdateSerializer(serializers.ModelSerializer):
    exp_month = serializers.IntegerField(write_only=True, required=True)
    exp_year = serializers.IntegerField(write_only=True, required=True)

    class Meta:
        model = PaymentMethod
        fields = ['exp_month', 'exp_year', 'payment_method_id']

    def update(self, instance, validated_data):
        card_token = retrieve_card_token(instance.token_id)
        if not card_token:
            raise serializers.ValidationError({'error': _('Invalida token![SP-106]')})
        try:
            modify_payment_method(instance.payment_method_id, validated_data)
            return instance
        except StripeError as e:
            raise serializers.ValidationError({'error': _(e.user_message + '[SP-107]')})
        except Exception as e:
            raise serializers.ValidationError({'error': _('Failed to update payment method.[SP-108]')})


class StripePaymentSerializer(serializers.ModelSerializer):
    payment_method_id = serializers.CharField(write_only=True, required=True)
    
    class Meta:
        model = StripePayment
        fields = ['user', 'subscription_id', 'payment_method_id']

        extra_kwargs = {
            'user': {
                'read_only': True
            },
            'subscription_id': {
                'read_only': True
            }
        }

    def create(self, validated_data):
        request_user = self.context['request'].user
        payment_method_id = validated_data.pop('payment_method_id')
        try:
            customer = request_user.stripe_payment
            customer_id = customer.customer_id
        except Exception as e:
            raise serializers.ValidationError({'error': _('Stripe customer not found.[SP-116]')})

        if customer.status == '1':
            raise serializers.ValidationError({'error': _('You already have an active subscription.Cancel it first & try again.[SP-117]')})

        check_exists = PaymentMethod.objects.filter(customer=customer.id, payment_method_id=payment_method_id)
        if not check_exists.exists():
            raise serializers.ValidationError({'error': _('Invalid payment method.[SP-118]')})

        try:
            pricing_plan = retrieve_pricing_plan(settings.STRIPE_ANNUAL_PRICE_PLAN_ID)
            customer_default_payment_method(customer_id, payment_method_id)
        except StripeError as e:
            raise serializers.ValidationError({'error': _(e.user_message + '[SP-119]')})
        except Exception as e:
            raise serializers.ValidationError({'error': _(str(e) + '[SP-120]')})

        try:
            # -1=incomplete, 0=inavtive, 1=active
            if customer.status == '0':
                pi = create_payment_intent(pricing_plan, request_user.email, customer_id, payment_method_id)
                subscription = create_stripe_subscription(customer_id, payment_method_id, pricing_plan.id)
                confirm_payment_intent(pi.id)
                # latest_invoice = latest_subscription_invoice(subscription.latest_invoice)
                # confirm_payment_intent(latest_invoice.payment_intent)
            elif customer.status == '-1':
                trial_days = pricing_plan.recurring.trial_period_days
                subscription = create_trial_subscription(customer_id, pricing_plan.id, trial_days)

        except StripeError as e:
            raise serializers.ValidationError({'error': _(e.user_message + '[SP-121]')})
        except Exception as e:
            raise serializers.ValidationError({'error': _(str(e) + '[SP-122]')})

        customer.payment_method_id = payment_method_id
        customer.subscription_id = subscription.id
        customer.status = 1
        customer.save()

        payment_method = PaymentMethod.objects.filter(customer=customer)
        payment_method.update(is_default=0)
        payment_method.filter(
            payment_method_id=payment_method_id).update(is_default=1)
        return customer


class StripePaymentUpdateSerializer(serializers.ModelSerializer):
    DEFAULT_CHOICES = (
        ('0', 'no'),
        ('1', 'yes')
    )
    is_cancel = serializers.ChoiceField(write_only=True, required=True, choices=DEFAULT_CHOICES)

    class Meta:
        model = StripePayment
        fields = ['is_cancel', 'user', 'subscription_id']

        extra_kwargs = {
            'user': {
                'read_only': True
            }
        }

    def update(self, instance, validated_data):
        data = validated_data
        if instance.status != '1':
            raise serializers.ValidationError({'error': _('Invalid subscription id![SP-151]')})
        if instance.is_cancel == data['is_cancel']:
            raise serializers.ValidationError({'error': _('Already updated this value.[SP-152]')})
        try:
            if data['is_cancel'] == '1':
                cancel_stripe_subscription(instance.subscription_id)
                instance.is_cancel = 1
            elif data['is_cancel'] == '0':
                not_cancel_stripe_subscription(instance.subscription_id)
                instance.is_cancel = 0
            instance.save()
            return instance
        except StripeError as e:
            raise serializers.ValidationError({'error': _(e.user_message + '[SP-153]')})
        except Exception as e:
            raise serializers.ValidationError({'error': _(str(e) + '[SP-154]')})
