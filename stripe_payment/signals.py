from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from .utils import create_stripe_customer, stripe_customer_delete
from .models import StripePayment

from stripe.error import StripeError
from django.contrib.auth.models import User
from django.contrib.auth import get_user_model
User = get_user_model()


@receiver(post_save, sender=User)
def stripe_customer_post_save(sender, instance, created, **kwargs):
    if created and instance.is_superuser is not True:
        try:
            customer = create_stripe_customer(user=instance)
            import datetime
            extend_time = datetime.datetime.now()
            StripePayment.objects.create(
                user=instance,
                customer_id=customer.id,
                paid_until=round(extend_time.timestamp()),
                status='-1'  # -1=incomplete, 0=inavtive, 1=active
            ) 
        except StripeError as e:
            print(e.user_message)
        except Exception as e:
            print(e)


@receiver(post_delete, sender=User)
def stripe_customer_post_delete(sender, instance, *args, **kwargs):
    stripe_customer = StripePayment.objects.filter(user=instance)[0]
    if stripe_customer.customer_id:
        try:
            stripe_customer_delete(customer_id=stripe_customer.customer_id)
        except StripeError as e:
            print(e.user_message)
        except Exception as e:
            print(e)
