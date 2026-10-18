import requests
from django.conf import settings


def get_paymob_payment_url(order, integration_id, payment_method):
    """
    هذه الدالة تقوم بتنفيذ الخطوات المطلوبة من Paymob
    لإرجاع رابط صفحة الدفع (Iframe للفيزا أو رابط مباشر للمحافظ وإنستاباي)
    """

    # الخطوة 1: الحصول على Authentication Token
    auth_url = "https://accept.paymobsolutions.com/api/auth/tokens"
    auth_response = requests.post(auth_url, json={"api_key": settings.PAYMOB_API_KEY})

    if auth_response.status_code != 201:
        print("Paymob Auth Error:", auth_response.text)
        return None

    auth_token = auth_response.json().get("token")

    # الخطوة 2: تسجيل الطلب (Order Registration)
    order_url = "https://accept.paymobsolutions.com/api/ecommerce/orders"
    # Paymob تطلب المبلغ بالقروش (Cents)
    amount_cents = int(order.total_price * 100)

    order_data = {
        "auth_token": auth_token,
        "delivery_needed": "false",
        "amount_cents": str(amount_cents),
        "currency": "EGP",
        "merchant_order_id": str(order.id),  # لتجنب التكرار في حالة تحديث الطلب
    }
    order_response = requests.post(order_url, json=order_data)

    if order_response.status_code != 201:
        print("Paymob Order Error:", order_response.text)
        return None

    paymob_order_id = order_response.json().get("id")

    # الخطوة 3: الحصول على مفتاح الدفع (Payment Key)
    payment_key_url = "https://accept.paymobsolutions.com/api/acceptance/payment_keys"

    # Paymob تتطلب بيانات العميل حتى لو كانت وهمية
    billing_data = {
        "apartment": "NA",
        "email": order.user.email if order.user.email else "test@example.com",
        "floor": "NA",
        "first_name": order.name.split()[0] if order.name else "Client",
        "street": order.address if order.address else "NA",
        "building": "NA",
        "phone_number": order.phone if order.phone else "01000000000",
        "shipping_method": "NA",
        "postal_code": "NA",
        "city": order.city if order.city else "Cairo",
        "country": "EG",
        "last_name": order.name.split()[-1] if len(order.name.split()) > 1 else "Name",
        "state": "NA",
    }

    payment_key_data = {
        "auth_token": auth_token,
        "amount_cents": str(amount_cents),
        "expiration": 3600,
        "order_id": paymob_order_id,
        "billing_data": billing_data,
        "currency": "EGP",
        "integration_id": integration_id,
    }

    payment_key_response = requests.post(payment_key_url, json=payment_key_data)

    if payment_key_response.status_code != 201:
        print("Paymob Payment Key Error:", payment_key_response.text)
        return None

    payment_token = payment_key_response.json().get("token")

    # ==========================================
    # الخطوة 4: التوجيه الذكي (Iframe للبطاقات / Iframe للمحافظ)
    # ==========================================
    if payment_method == "card":
        # 🔴 توجيه العميل لإيفريم الفيزا
        iframe_url = f"https://accept.paymobsolutions.com/api/acceptance/iframes/{settings.PAYMOB_CARD_IFRAME_ID}?payment_token={payment_token}"
        return iframe_url

    elif payment_method in ["wallet", "instapay"]:
        # 🔴 توجيه العميل لإيفريم المحافظ
        iframe_url = f"https://accept.paymobsolutions.com/api/acceptance/iframes/{settings.PAYMOB_WALLET_IFRAME_ID}?payment_token={payment_token}"
        return iframe_url

    return None
