from rest_framework.viewsets import ModelViewSet
from rest_framework.views import APIView
from django.utils.translation import ugettext_lazy as _

from rest_framework.authentication import TokenAuthentication, SessionAuthentication
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.decorators import api_view, authentication_classes, permission_classes

from django.views.decorators.csrf import csrf_exempt
from rest_framework.response import Response
from django.http import HttpResponse
from rest_framework import status

from stripe_payment.models import *
from .serializers import *
from stripe_payment.utils import *


class PaymentMethodView(ModelViewSet):
    authentication_class = [TokenAuthentication, SessionAuthentication]
    permission_class = [IsAuthenticated]
    queryset = None

    def get_serializer_class(self):
        if self.action in ["list", "retrieve"]:
            return PaymentMethodDetailsSerializer
        elif self.action == 'update':
            return PaymentMethodUpdateSerializer
        return PaymentMethodSerializer

    def get_queryset(self):
        return PaymentMethod.objects.filter(user=self.request.user).filter(status=1)


    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        if not obj:
            raise serializers.ValidationError({'error': _('Payment method not found!.[SP-112]')})
        if obj.is_default == '1':
            raise serializers.ValidationError({'error': _('Default card not remove. Change default card & try again.[SP-113]')})
        try:
            detach_payment_method(obj.payment_method_id)
            obj.delete()
            return Response({'success': _('Card remvove successfully')}, status=status.HTTP_204_NO_CONTENT)
        except StripeError as e:
            raise serializers.ValidationError({'error': _(e.user_message + '[SP-114]')})
        except Exception as e:
            raise serializers.ValidationError({'error': _(str(e) + '[SP-115]')})


class StripePaymentView(ModelViewSet):
    authentication_class = [TokenAuthentication, SessionAuthentication]
    permission_class = [IsAuthenticated]
    http_method_names = ['post', 'put']
    queryset = None
    
    def get_serializer_class(self):
        if self.action == 'update':
            return StripePaymentUpdateSerializer
        return StripePaymentSerializer

    def get_queryset(self):
        return StripePayment.objects.filter(user=self.request.user)


class Config(APIView):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated, ]

    def get(self, request):
        try:
            from django.conf import settings
            publishable_key = settings.STRIPE_TEST_PUBLISHABLE_KEY1
            if not settings.DEBUG:
                publishable_key = settings.STRIPE_LIVE_PUBLISHABLE_KEY1
            return Response({'publishable_key': publishable_key})
        except Exception as e:
            raise serializers.ValidationError({'error': _('Stripe publishable key not found! [SP-141]')})


@api_view(['POST'])
@csrf_exempt
@permission_classes([AllowAny])
def stripe_webhooks(request):
    payload = request.body
    sig_header = request.META['HTTP_STRIPE_SIGNATURE']
    event = None
    try:
        from django.conf import settings
        web_secret = settings.STRIPE_WEBHOOK_SIGNING_KEY
        event = stripe.Webhook.construct_event(payload, sig_header, web_secret)
    except ValueError:
        return HttpResponse('Invalid payload![SP-171]', status=status.HTTP_400_BAD_REQUEST)
    except stripe.error.SignatureVerificationError:
        return HttpResponse(_(e.user_message + '[SP-172]'), status=status.HTTP_400_BAD_REQUEST)

    # Handle the event
    if event.type == 'charge.succeeded':
        try:
            payment_intent = retrieve_payment_intent(event.data.object.payment_intent)

            if not payment_intent.customer:
                return HttpResponse('This was one time payment[SP-173]', status=status.HTTP_400_BAD_REQUEST)

            customer = retrieve_stripe_customer(payment_intent.customer)
        except StripeError as e:
            return HttpResponse(_(e.user_message + '[SP-174]'), status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return HttpResponse(_(str(e) + '[SP-175]'), status=status.HTTP_400_BAD_REQUEST)

        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.get(**{User.EMAIL_FIELD: customer.email})
        except User.DoesNotExit:
            return HttpResponse('User does not exit![SP-176]', status=status.HTTP_400_BAD_REQUEST)

        stripe_customer = StripePayment.objects.get(user_id=user.id)
        subscription = retrieve_customer_subscription(stripe_customer.subscription_id)

        from django.db.models import F
        stripe_customer.no_of_subscriptions = F('no_of_subscriptions')+1
        stripe_customer.paid_until = subscription['current_period_end']
        stripe_customer.status = 1
        stripe_customer.save() 
        
    elif event.type == 'customer.subscription.created' or event.type == 'customer.subscription.updated':
        try:
            subscription = event.data.object.id
            customer = event.data.object.customer
            current_period_end = event.data.object.current_period_end
            StripePayment.objects.filter(customer_id=customer,subscription_id=subscription).update(paid_until=current_period_end,
                                                                                                   status='1')
        except Exception as e:
            return HttpResponse(_(str(e) + '[SP-176]'), status=status.HTTP_400_BAD_REQUEST)

    elif event.type == 'customer.subscription.deleted':
        try:
            subscription = event.data.object.id
            customer = event.data.object.customer
            StripePayment.objects.filter(customer_id=customer,subscription_id=subscription).update(payment_method_id='',
                                                                                                   subscription_id='',
                                                                                                   paid_until=0000,
                                                                                                   status='0',
                                                                                                   is_cancel='0')
        except Exception as e:
            return HttpResponse(_(str(e) + '[SP-177]'), status=status.HTTP_400_BAD_REQUEST)

    elif event.type == 'customer.deleted':
        try:
            customer_id = event.data.object.id
            stripe_cus = StripePayment.objects.filter(
                customer_id=customer_id)[0]
            PaymentMethod.objects.filter(user_id=stripe_cus.user_id).delete()
            stripe_cus.delete()
        except Exception as e:
            return HttpResponse(_(str(e) + '[SP-178]'), status=status.HTTP_400_BAD_REQUEST)
            
    # pending
    elif event.type == 'customer.subscription.trial_will_end':
        print('trial will end')
        pass
             
    return HttpResponse('Successfully received request.', status=status.HTTP_200_OK)
