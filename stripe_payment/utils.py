from django.conf import settings
import stripe
from stripe.error import StripeError

from .models import *

# stripe_api_key = settings.STRIPE_LIVE_SECRET_KEY
stripe_api_key = settings.STRIPE_TEST_SECRET_KEY
if settings.DEBUG:
    stripe_api_key = settings.STRIPE_TEST_SECRET_KEY
stripe.api_key = stripe_api_key


def create_stripe_customer(user):
    return stripe.Customer.create(
        name=user.name,
        email=user.email,
        metadata={
            'user_id': user.id
        }
    )


def app_create_stripe_customer(user):
    stripe_customer = create_stripe_customer(user)
    if stripe_customer:
        import datetime
        extend_time = datetime.datetime.now()
        from .models import StripePayment
        return StripePayment.objects.create(user_id=user.id,
                                            customer_id=stripe_customer.id,
                                            paid_until=round(extend_time.timestamp()),
                                            status='-1')  # -1=incomplete, 0=inavtive, 1=active
    return None


def stripe_customer_delete(customer_id, user_id=None):
    return stripe.Customer.delete(customer_id)


def retrieve_stripe_customer(customer_id):
    return stripe.Customer.retrieve(customer_id)


def customer_default_payment_method(customer_id, payment_method_id):
    return stripe.Customer.modify(customer_id,
        invoice_settings={
            'default_payment_method': payment_method_id
        }
    )


def create_card_token(data):
    return stripe.Token.create(
        card={
            "number": data['number'],
            "exp_month": data['exp_month'],
            "exp_year": data['exp_year'],
            "cvc": data['cvc']
        }
    )


def retrieve_card_token(token):
    return stripe.Token.retrieve(token)


def retrieve_stripe_product(product_id):
    return stripe.Product.retrieve(product_id)


def retrieve_pricing_plan(id):
    return stripe.Price.retrieve(id)


def create_payment_intent(data, email, customer_Id, payment_method_id):
    return stripe.PaymentIntent.create(
        customer=customer_Id,
        amount=data.unit_amount,
        currency=data.currency,
        payment_method_types=["card"],
        payment_method=payment_method_id,
        receipt_email=email,
        capture_method="automatic",
    )
    

def retrieve_payment_intent(payment_intent_id):
    return stripe.PaymentIntent.retrieve(payment_intent_id)


def modify_payment_intent(payment_intent_id, payment_method_id, customer_id):
    return stripe.PaymentIntent.modify(payment_intent_id, 
        payment_mehthod_id=payment_method_id,
        customer=customer_id
    )


def confirm_payment_intent(intent_id):
    return stripe.PaymentIntent.confirm(intent_id)


def create_payment_method(data, user):
    return stripe.PaymentMethod.create(
        type="card",
        card={
            "number": data['number'],
            "exp_month": data['exp_month'],
            "exp_year": data['exp_year'],
            "cvc": data['cvc'],
        },
        billing_details={
            'email': user.email,
            'name': user.username,
        }
    )


def retrieve_payment_method(payment_method_id):
    return stripe.PaymentMethod.retrieve(payment_method_id)


def modify_payment_method(payment_method_id, data):
    return stripe.PaymentMethod.modify(
        payment_method_id,
        card={
            "exp_month": data['exp_month'],
            "exp_year": data['exp_year']
        },
    )


def attach_payment_method(payment_method_id, customer_id):
    return stripe.PaymentMethod.attach(payment_method_id, 
        customer=customer_id,
    )


def detach_payment_method(payment_method_id):
    return stripe.PaymentMethod.detach(payment_method_id)


def create_trial_subscription(customer_id, price_id, trial_days):
    if trial_days is None:
        trial_days=7 # default 7 days
    from django.utils.timezone import timedelta
    import datetime
    trial_end = datetime.datetime.now() + timedelta(days=trial_days)
    
    return stripe.Subscription.create(customer=customer_id,
        items=[{
            'price': price_id
        }],
        trial_end=trial_end
    )


def create_stripe_subscription(customer_id, payment_method_id, pricing_plan_id):
    return stripe.Subscription.create(
        customer=customer_id,
        items=[{
            'price': pricing_plan_id
        }],
        default_payment_method=payment_method_id,
        trial_end='now'
    )


def cancel_stripe_subscription(subscription_id):
    return stripe.Subscription.modify(subscription_id,
        cancel_at_period_end=True
    )


def not_cancel_stripe_subscription(subscription_id):
    return stripe.Subscription.modify(subscription_id,
        cancel_at_period_end=False
    )


def retrieve_customer_subscription(subscription_id):
    return stripe.Subscription.retrieve(subscription_id)


def latest_subscription_invoice(latest_invoice_id):
    return stripe.Invoice.retrieve(latest_invoice_id)
