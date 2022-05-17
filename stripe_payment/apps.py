from django.apps import AppConfig


class StripePaymentConfig(AppConfig):
    name = 'stripe_payment'

    def ready(self):
        try:
            import stripe_payment.signals
        except ImportError:
            pass
