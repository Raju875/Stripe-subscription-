from rest_framework.authtoken.models import Token
from django.utils.translation import ugettext_lazy as _
from django.http import HttpResponse
from rest_framework import status

from .models import StripePayment
from .utils import app_create_stripe_customer


class PaymentMiddleware(object):

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        if view_func.__module__ in set({'stripe_payment.api.v1.views', 'stripe_wallet.api.v1.views'}):
            return None

        header_token = request.META.get('HTTP_AUTHORIZATION', None)
        if header_token is None:
            return None
        token = header_token.split()[1]

        try:
            token_obj = Token.objects.get(key=token)
            user = token_obj.user
            if user.is_superuser:
                return None
            stripe_customer = StripePayment.objects.filter(user=user).first()

            if stripe_customer is None:
                stripe_customer = app_create_stripe_customer(user)

            # -1=incomplete, 0=inavtive, 1=active
            if stripe_customer.status == '-1':
                return HttpResponse(_('Apply for free trial.'), status=status.HTTP_403_FORBIDDEN)
            elif stripe_customer.status == '0':
                return HttpResponse(_('You have no subscription.'), status=status.HTTP_403_FORBIDDEN)
            elif stripe_customer.status == '1':
                import time
                if round(time.time()) > int(stripe_customer.paid_until):
                    return HttpResponse(_('Subscription expired.'), status=status.HTTP_403_FORBIDDEN)
            else:
                return HttpResponse(_('Invalid payment stattus.[SP-191]'), status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            print(e)
            import sys
            import os
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            return HttpResponse(_(str(e) + '(' + fname + '-' + str(exc_tb.tb_lineno) + ')[SP-199]'), status=status.HTTP_400_BAD_REQUEST)
