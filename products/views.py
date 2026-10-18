# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import csv
import json
import os
import threading
from datetime import timedelta
from decimal import Decimal
from urllib.parse import quote

import gspread
from google import genai
from google.genai import types
from google.oauth2.service_account import Credentials
from PIL import Image

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.contrib.auth.signals import user_logged_in
from django.core.mail import EmailMultiAlternatives
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db import transaction
from django.db.models import Count, F, Q, Sum
from django.dispatch import receiver
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.html import strip_tags
from django.utils.timesince import timesince
from django.utils.timezone import localtime
from django.utils.translation import gettext as _
from django.views.decorators.cache import never_cache

from .forms import CouponForm, ProductForm, ReviewForm
from .models import (
    Cart,
    CartItem,
    Coupon,
    Notification,
    Order,
    OrderItem,
    Product,
    ProductAccord,
    ProductImage,
    Review,
    UserProfile,
    Wishlist,
)
from .paymob import get_paymob_payment_url


# ==========================================
# دالة التحقق من صلاحية الإدارة
# ==========================================
def is_admin(user):
    return user.is_superuser or user.is_staff


# ==========================================
# 🤖 مستشار العطور بالذكاء الاصطناعي (AI Perfume Finder)
# ==========================================
@never_cache
def ai_perfume_finder(request):
    """عرض صفحة مستشار العطور الذكي"""
    return render(request, 'products/ai_finder.html')


@never_cache
def api_recommend_perfumes(request):
    """API يستقبل تفضيلات العميل ويرجع ترشيحات بالعربي أو الإنجليزي حسب لغة الموقع"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body)
        lang = data.get('lang') or getattr(request, 'LANGUAGE_CODE', 'ar')
        is_en = 'en' in str(lang).lower()

        season = data.get('season', 'Any' if is_en else 'أي فصل')
        time_of_day = data.get('time_of_day', 'Any' if is_en else 'أي وقت')
        strength = data.get('strength', 'Moderate to Strong' if is_en else 'متوسط إلى قوي')
        gender = data.get('gender', 'Unisex' if is_en else 'للجنسين')
        notes = data.get('notes', '')
        extra_details = data.get('extra_details', '')

        # 1. جلب العطور المتاحة من قاعدة البيانات مع النوتات العطرية (ProductAccord)
        products = Product.objects.prefetch_related('accords', 'images').all()
        if not products.exists():
            err_msg = 'No perfumes available in stock currently.' if is_en else 'لا توجد عطور متاحة حالياً في المتجر.'
            return JsonResponse({'error': err_msg}, status=404)

        catalog_list = []
        products_map = {}
        for p in products:
            products_map[p.id] = p
            accords_qs = p.accords.all() if hasattr(p, 'accords') else p.productaccord_set.all()

            if is_en:
                accords_text = ", ".join([(getattr(a, 'name_en', '') or a.name) for a in accords_qs if a.name])
                prod_name = getattr(p, 'name_en', '') or p.name
                prod_desc = getattr(p, 'description_en', '') or getattr(p, 'description', '')
            else:
                accords_text = "، ".join([a.name for a in accords_qs if a.name])
                prod_name = p.name
                prod_desc = getattr(p, 'description', '')

            catalog_list.append({
                "id": p.id,
                "name": prod_name,
                "category": getattr(p, 'category', ''),
                "description": (prod_desc or '')[:300],
                "accords": accords_text,
                "price": str(getattr(p, 'price', '')),
            })

        ai_result = None
        api_key = getattr(settings, 'GEMINI_API_KEY', None) or os.getenv('GEMINI_API_KEY')

        # 2. محاولة التحليل عبر Google Gemini AI باللغة المطلوبة
        if api_key:
            try:
                client = genai.Client(api_key=api_key)
                lang_instruction = (
                    "Write 'intro_message' and 'reason' strictly in elegant English."
                    if is_en else
                    "اكتب 'intro_message' و 'reason' باللغة العربية بأسلوب فخم وجذاب."
                )

                prompt = f"""
                You are a world-class perfume expert at 'Luxury Perfumes'.
                Customer preferences:
                - Gender: {gender} | Season: {season} | Occasion: {time_of_day} | Projection/Strength: {strength}
                - Favorite Notes: {notes} | Extra Details: {extra_details}

                Available Perfumes Catalog:
                {json.dumps(catalog_list, ensure_ascii=False)}

                Instructions:
                1. Pick the best 2 or 3 perfumes from the catalog above ONLY (use their exact 'id').
                2. {lang_instruction}
                3. Return valid JSON ONLY in this exact format:
                {{
                    "intro_message": "...",
                    "recommendations": [
                        {{
                            "product_id": 1,
                            "match_percentage": 98,
                            "reason": "..."
                        }}
                    ]
                }}
                """

                for model_name in ['gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-1.5-flash']:
                    try:
                        response = client.models.generate_content(
                            model=model_name,
                            contents=prompt,
                        )
                        raw_text = response.text.strip()
                        if "```" in raw_text:
                            raw_text = raw_text.split("```")[1]
                            if raw_text.startswith("json"):
                                raw_text = raw_text[4:]
                        ai_result = json.loads(raw_text.strip())
                        break
                    except Exception:
                        continue
            except Exception as ai_err:
                print(f"Gemini API Error: {ai_err}")

        # 3. تجهيز النتيجة النهائية
        final_recommendations = []
        default_intro = (
            "Here are the finest perfumes curated exclusively for your taste:"
            if is_en else
            "إليك أرقى العطور المختارة خصيصاً لتناسب ذوقك وشخصيتك:"
        )
        intro_message = default_intro

        if ai_result and ai_result.get('recommendations'):
            intro_message = ai_result.get('intro_message', default_intro)
            for rec in ai_result.get('recommendations', []):
                try:
                    pid = int(rec.get('product_id'))
                except (ValueError, TypeError):
                    continue
                if pid in products_map:
                    prod = products_map[pid]
                    display_name = (getattr(prod, 'name_en', '') or prod.name) if is_en else prod.name
                    image_url = prod.image.url if getattr(prod, 'image', None) else ''
                    try:
                        detail_url = reverse('product_detail', args=[prod.id])
                    except Exception:
                        detail_url = f"/product/{prod.id}/"

                    final_recommendations.append({
                        'id': prod.id,
                        'name': display_name,
                        'price': str(prod.price),
                        'image_url': image_url,
                        'detail_url': detail_url,
                        'match_percentage': rec.get('match_percentage', 96),
                        'reason': rec.get('reason', '')
                    })

        # 4. نظام الإنقاذ الذكي (Fallback) بنفس لغة الموقع
        if not final_recommendations:
            notes_keywords = [n.strip().lower() for n in notes.replace('،', ',').split(',') if n.strip()]
            scored_products = []
            for item in catalog_list:
                score = 88
                search_blob = f"{item['name']} {item['description']} {item['accords']}".lower()
                for kw in notes_keywords:
                    if kw in search_blob:
                        score += 4
                if extra_details and extra_details.lower() in search_blob:
                    score += 5
                scored_products.append((min(score, 99), products_map[item['id']], item['name'], item['accords']))

            scored_products.sort(key=lambda x: x[0], reverse=True)
            for idx, (score, prod, disp_name, acc_text) in enumerate(scored_products[:3]):
                image_url = prod.image.url if getattr(prod, 'image', None) else ''
                try:
                    detail_url = reverse('product_detail', args=[prod.id])
                except Exception:
                    detail_url = f"/product/{prod.id}/"

                if is_en:
                    notes_mention = f"featuring rich notes of ({acc_text})" if acc_text else "with its luxurious signature"
                    reason_text = f"An ideal choice for ({season}) and ({time_of_day}), {notes_mention} with ({strength}) performance."
                else:
                    notes_mention = f"بفضل تركيبته الغنية بـ ({acc_text})" if acc_text else "لطابعه الفاخر والمميز"
                    reason_text = f"خيار مثالي لأجواء ({season}) و({time_of_day}) {notes_mention} مع ثبات وفوحان ({strength}) يليق بذوقك."

                final_recommendations.append({
                    'id': prod.id,
                    'name': disp_name,
                    'price': str(prod.price),
                    'image_url': image_url,
                    'detail_url': detail_url,
                    'match_percentage': score - (idx * 2),
                    'reason': reason_text
                })

        return JsonResponse({
            'status': 'success',
            'intro_message': intro_message,
            'recommendations': final_recommendations
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ==========================================
# المصادقة والحسابات (Auth)
# ==========================================
@never_cache
def login_view(request):
    if request.user.is_authenticated:
        if is_admin(request.user):
            return redirect("dashboard_product_list")
        return redirect("user_product_list")

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            if is_admin(user):
                return redirect("dashboard_product_list")
            return redirect("user_product_list")

        return render(request, "products/login.html", {"error": _("بيانات الدخول غير صحيحة")})

    return render(request, "products/login.html")


def logout_view(request):
    logout(request)
    return redirect("login")


@never_cache
def register_view(request):
    form = UserCreationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect("user_product_list")

    return render(request, "products/register.html", {"form": form})


# ==========================================
# المتجر وواجهة العميل (Shop & Products)
# ==========================================
def home(request):
    latest_products = Product.objects.prefetch_related('accords', 'images').all().order_by('-id')[:4]
    best_sellers = Product.objects.prefetch_related('accords', 'images').all().order_by('?')[:4]

    wishlist_product_ids = []
    if request.user.is_authenticated:
        wishlist_product_ids = Wishlist.objects.filter(user=request.user).values_list(
            "product_id", flat=True
        )

    return render(request, "products/home.html", {
        "latest_products": latest_products,
        "best_sellers": best_sellers,
        "wishlist_product_ids": wishlist_product_ids,
    })


def user_product_list(request):
    products_list = Product.objects.prefetch_related('accords', 'images').all().order_by("-id")

    search_query = request.GET.get("q")
    if search_query:
        products_list = products_list.filter(
            Q(name__icontains=search_query) | Q(description__icontains=search_query)
        )

    category = request.GET.get("category")
    if category and category != 'all':
        products_list = products_list.filter(category=category)

    sort_by = request.GET.get("sort")
    if sort_by == "price_low":
        products_list = products_list.order_by("price")
    elif sort_by == "price_high":
        products_list = products_list.order_by("-price")

    wishlist_product_ids = []
    if request.user.is_authenticated:
        wishlist_product_ids = Wishlist.objects.filter(user=request.user).values_list(
            "product_id", flat=True
        )

    page = request.GET.get("page", 1)
    paginator = Paginator(products_list, 12)

    try:
        page_obj = paginator.page(page)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    context = {
        'products': page_obj,
        'page_obj': page_obj,
        'wishlist_product_ids': wishlist_product_ids,
    }

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        html = render_to_string(
            'products/partials/product_grid.html',
            context,
            request=request
        )
        return JsonResponse({'html': html})

    return render(request, "products/user_product_list.html", context)


@never_cache
def product_detail(request, id):
    product = get_object_or_404(Product, id=id)
    related_products = Product.objects.filter(category=product.category).exclude(id=product.id)[:4]
    reviews = product.reviews.all().order_by("-created_at")

    total_reviews = reviews.count()
    rating_counts = {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}

    for r in reviews:
        if hasattr(r, 'rating') and r.rating in rating_counts:
            rating_counts[r.rating] += 1

    rating_percentages = {
        star: (count / total_reviews * 100) if total_reviews > 0 else 0
        for star, count in rating_counts.items()
    }

    if request.method == "POST":
        if request.user.is_authenticated:
            form = ReviewForm(request.POST)
            if form.is_valid():
                review = form.save(commit=False)
                review.product = product
                review.user = request.user
                review.save()
                return redirect("product_detail", id=product.id)
        else:
            return redirect("login")
    else:
        form = ReviewForm()

    return render(
        request,
        "products/product_detail.html",
        {
            "product": product,
            "reviews": reviews,
            "form": form,
            "related_products": related_products,
            "rating_counts": rating_counts,
            "rating_percentages": rating_percentages,
        },
    )


# ==========================================
# سلة المشتريات (Cart Logic)
# ==========================================
def add_to_cart(request, id):
    product = get_object_or_404(Product, id=id)
    size = request.GET.get("size", "50")

    if request.user.is_authenticated:
        cart, created = Cart.objects.get_or_create(user=request.user)
        cart_item, item_created = CartItem.objects.get_or_create(
            cart=cart,
            product=product,
            size=size,
        )
        if not item_created:
            cart_item.quantity += 1
            cart_item.save()

        cart.abandoned_email_sent = False
        cart.save()
    else:
        cart = request.session.get("cart", {})
        cart_key = f"{id}_{size}"
        if cart_key in cart:
            cart[cart_key] += 1
        else:
            cart[cart_key] = 1
        request.session["cart"] = cart
        request.session.modified = True

    messages.success(request, _("تمت إضافة %(name)s إلى السلة بنجاح! 🛒") % {'name': product.name})

    previous_url = request.META.get("HTTP_REFERER")
    return redirect(previous_url if previous_url else "user_product_list")


@never_cache
def cart_view(request):
    products = []
    total = Decimal("0.00")

    if request.user.is_authenticated:
        cart, created = Cart.objects.get_or_create(user=request.user)
        cart_items = cart.items.all()

        for item in cart_items:
            product = item.product
            size = item.size
            quantity = item.quantity

            if size == "30" and product.price_30:
                current_price = product.price_30
            elif size == "50" and product.price_50:
                current_price = product.price_50
            elif size == "100" and product.price_100:
                current_price = product.price_100
            else:
                current_price = product.price

            product.quantity = quantity
            product.price = current_price
            product.total_price = current_price * quantity
            product.selected_size = size
            product.unique_cart_key = f"{product.id}_{size}"

            total += product.total_price
            products.append(product)

    else:
        cart = request.session.get("cart", {})
        legacy_keys = [key for key in cart.keys() if "_" not in str(key)]
        for k in legacy_keys:
            del cart[k]

        if legacy_keys:
            request.session["cart"] = cart
            request.session.modified = True

        items_to_remove = []
        for cart_key, quantity in cart.items():
            try:
                parts = str(cart_key).split("_")
                product_id = parts[0]
                size = parts[1] if len(parts) > 1 else "50"

                product = Product.objects.get(id=product_id)

                if size == "30" and product.price_30:
                    current_price = product.price_30
                elif size == "50" and product.price_50:
                    current_price = product.price_50
                elif size == "100" and product.price_100:
                    current_price = product.price_100
                else:
                    current_price = product.price

                product.quantity = quantity
                product.price = current_price
                product.total_price = current_price * quantity
                product.selected_size = size
                product.unique_cart_key = cart_key

                total += product.total_price
                products.append(product)

            except Product.DoesNotExist:
                items_to_remove.append(cart_key)

        if items_to_remove:
            for item in items_to_remove:
                del cart[item]
            request.session["cart"] = cart
            request.session.modified = True

    return render(request, "products/cart.html", {"products": products, "total": total})


def increase_cart(request, cart_key):
    if request.user.is_authenticated:
        parts = str(cart_key).split("_")
        product_id = parts[0]
        size = parts[1] if len(parts) > 1 else "50"
        try:
            cart = Cart.objects.get(user=request.user)
            cart_item = CartItem.objects.get(cart=cart, product=product_id, size=size)
            cart_item.quantity += 1
            cart_item.save()
        except (Cart.DoesNotExist, CartItem.DoesNotExist):
            pass
    else:
        cart = request.session.get("cart", {})
        if cart_key in cart:
            cart[cart_key] += 1
        request.session["cart"] = cart
        request.session.modified = True

    return redirect("cart")


def decrease_cart(request, cart_key):
    if request.user.is_authenticated:
        parts = str(cart_key).split("_")
        product_id = parts[0]
        size = parts[1] if len(parts) > 1 else "50"
        try:
            cart = Cart.objects.get(user=request.user)
            cart_item = CartItem.objects.get(cart=cart, product=product_id, size=size)
            if cart_item.quantity > 1:
                cart_item.quantity -= 1
                cart_item.save()
            else:
                cart_item.delete()
        except (Cart.DoesNotExist, CartItem.DoesNotExist):
            pass
    else:
        cart = request.session.get("cart", {})
        actual_key = (
            cart_key if cart_key in cart
            else (int(cart_key) if str(cart_key).isdigit() and int(cart_key) in cart else None)
        )
        if actual_key is not None:
            if cart[actual_key] > 1:
                cart[actual_key] -= 1
            else:
                del cart[actual_key]
        request.session["cart"] = cart
        request.session.modified = True

    return redirect("cart")


def remove_from_cart(request, cart_key):
    if request.user.is_authenticated:
        parts = str(cart_key).split("_")
        product_id = parts[0]
        size = parts[1] if len(parts) > 1 else "50"
        try:
            cart = Cart.objects.get(user=request.user)
            CartItem.objects.filter(cart=cart, product=product_id, size=size).delete()
        except Cart.DoesNotExist:
            pass
    else:
        cart = request.session.get("cart", {})
        if cart_key in cart:
            del cart[cart_key]
        elif str(cart_key).isdigit() and int(cart_key) in cart:
            del cart[int(cart_key)]
        request.session["cart"] = cart
        request.session.modified = True

    return redirect("cart")


def clear_cart(request):
    if request.user.is_authenticated:
        CartItem.objects.filter(cart__user=request.user).delete()
    request.session["cart"] = {}
    request.session.modified = True
    return redirect("cart")


@receiver(user_logged_in)
def merge_cart_on_login(sender, user, request, **kwargs):
    session_cart = request.session.get("cart", {})
    if session_cart:
        cart, created = Cart.objects.get_or_create(user=user)
        for cart_key, quantity in session_cart.items():
            try:
                parts = str(cart_key).split("_")
                product_id = parts[0]
                size = parts[1] if len(parts) > 1 else "50"
                product = Product.objects.get(id=product_id)

                cart_item, item_created = CartItem.objects.get_or_create(
                    cart=cart, product=product, size=size
                )
                if not item_created:
                    cart_item.quantity += quantity
                else:
                    cart_item.quantity = quantity
                cart_item.save()
            except Product.DoesNotExist:
                continue

        request.session["cart"] = {}
        request.session.modified = True


# ==========================================
# الدفع والطلبات (Checkout & Orders)
# ==========================================
@login_required
@never_cache
def checkout_view(request):
    products = []
    total = Decimal("0.00")

    try:
        cart = Cart.objects.get(user=request.user)
        cart_items = cart.items.all()
    except Cart.DoesNotExist:
        cart_items = []

    for item in cart_items:
        product = item.product
        size = item.size
        quantity = item.quantity

        if size == "30" and product.price_30:
            current_price = product.price_30
        elif size == "50" and product.price_50:
            current_price = product.price_50
        elif size == "100" and product.price_100:
            current_price = product.price_100
        else:
            current_price = product.price

        product.quantity = quantity
        product.price = current_price
        product.total_price = current_price * quantity
        product.selected_size = size

        total += product.total_price
        products.append(product)

    discount_amount = Decimal("0.00")
    coupon_id = request.session.get("coupon_id")
    if coupon_id:
        try:
            coupon = Coupon.objects.get(id=coupon_id, active=True)
            discount_amount = (Decimal(coupon.discount) / Decimal("100")) * total
            total = total - discount_amount
        except Coupon.DoesNotExist:
            if "coupon_id" in request.session:
                del request.session["coupon_id"]
                request.session.modified = True

    user_profile = getattr(request.user, 'profile', None)

    return render(
        request,
        "products/checkout.html",
        {
            "products": products,
            "total": total,
            "discount_amount": discount_amount,
            "user_profile": user_profile,
        },
    )


# ==========================================
# 🤖 دالة فحص الإيصال بالذكاء الاصطناعي
# ==========================================
def check_payment_receipt_with_ai(image_file, expected_total):
    try:
        api_key = getattr(settings, 'GEMINI_API_KEY', None) or os.getenv('GEMINI_API_KEY')
        client = genai.Client(api_key=api_key)

        image_file.seek(0)
        img = Image.open(image_file)
        img.thumbnail((500, 500))

        prompt = f"""
        أنت محاسب مالي صارم يعمل في متجر عطور. هذه صورة إيصال تحويل مالي.
        المبلغ المطلوب دفعه هو: {expected_total}.
        مهمتك هي البحث في الصورة عن هذا الرقم.
        هل المبلغ المحول في الإيصال يطابق {expected_total} بالضبط؟
        أجب بكلمة واحدة فقط: "مطابق" أو "مرفوض".
        """

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[prompt, img]
        )
        image_file.seek(0)

        if "مطابق" in response.text:
            return True
        return False

    except Exception as e:
        print(f"Gemini AI Error: {e}")
        return str(e)


@login_required
@never_cache
def place_order(request):
    if request.method != "POST":
        return redirect("checkout")

    payment_method_input = request.POST.get("payment_method")
    payment_proof_file = request.FILES.get("payment_proof")
    district_input = request.POST.get("district")
    customer_email = request.POST.get("email")

    if payment_method_input in ["vodafone", "instapay_manual"]:
        if not payment_proof_file:
            messages.error(request, _("⚠️ يرجى رفع صورة إيصال التحويل لتأكيد طلبك."))
            return redirect("checkout")

    try:
        cart = Cart.objects.get(user=request.user)
        cart_items = cart.items.all()
    except Cart.DoesNotExist:
        return redirect("cart")

    if not cart_items.exists():
        return redirect("cart")

    total_products_price = Decimal("0.00")

    with transaction.atomic():
        order = Order.objects.create(
            user=request.user,
            name=request.POST.get("name"),
            phone=request.POST.get("phone"),
            city=request.POST.get("city"),
            district=district_input,
            address=request.POST.get("address"),
            payment_method=payment_method_input,
            payment_proof=payment_proof_file,
        )

        for item in cart_items:
            product = item.product
            size = item.size
            quantity = item.quantity

            if product.stock < quantity:
                transaction.set_rollback(True)
                messages.error(
                    request,
                    _("عذراً، الكمية المطلوبة من '%(name)s' غير متوفرة (المتاح: %(stock)s فقط).") % {
                        'name': product.name,
                        'stock': product.stock
                    }
                )
                return redirect("cart")

            product.stock -= quantity
            product.save()

            if size == "30" and product.price_30:
                current_price = product.price_30
                current_cost = product.cost_price_30 or product.cost_price
            elif size == "50" and product.price_50:
                current_price = product.price_50
                current_cost = product.cost_price_50 or product.cost_price
            elif size == "100" and product.price_100:
                current_price = product.price_100
                current_cost = product.cost_price_100 or product.cost_price
            else:
                current_price = product.price
                current_cost = product.cost_price

            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=quantity,
                price=current_price,
                size=size,
                cost_price=current_cost,
            )
            total_products_price += current_price * quantity

        coupon_id = request.session.get("coupon_id")
        if coupon_id:
            try:
                coupon = Coupon.objects.get(id=coupon_id, active=True)
                discount_fraction = Decimal(coupon.discount) / Decimal("100")
                discount_amount = discount_fraction * total_products_price
                total_products_price -= discount_amount

                del request.session["coupon_id"]
                request.session.modified = True
            except Coupon.DoesNotExist:
                pass

        shipping_cost_decimal = Decimal(str(order.shipping_cost))
        order.total_price = total_products_price + shipping_cost_decimal

        if payment_method_input in ["vodafone", "instapay_manual"] and payment_proof_file:
            ai_result = check_payment_receipt_with_ai(payment_proof_file, order.total_price)

            if ai_result is False:
                transaction.set_rollback(True)
                messages.error(request, _("❌ الإيصال المرفق غير مطابق لإجمالي الفاتورة (%(total)s ج.م)، أو الصورة غير واضحة. يرجى التأكد وإعادة الرفع.") % {'total': order.total_price})
                return redirect("checkout")
            elif isinstance(ai_result, str):
                messages.info(request, f"⚠️ عطل في الذكاء الاصطناعي: {ai_result}")
            else:
                messages.success(request, _("✅ تمت مطابقة الإيصال بواسطة الذكاء الاصطناعي. طلبك قيد التجهيز!"))

            order.payment_status = 'pending'

        order.stock_updated = True
        order.save()

        Notification.objects.create(
            order=order,
            message=f"تم استلام طلب جديد من: {order.name} 🛍️"
        )

    order.refresh_from_db()

    # إرسال الطلب إلى Google Sheets في الخلفية حتى لا يبطئ الموقع
    threading.Thread(target=send_order_to_google_sheet, args=(order,)).start()

    if customer_email and request.user.email != customer_email:
        request.user.email = customer_email
        request.user.save()

    def send_invoice_email_bg(order_obj, to_email):
        if to_email:
            try:
                subject = f"فاتورة طلبك رقم #{order_obj.id} - متجر العطور"
                html_message = render_to_string("products/emails/invoice.html", {"order": order_obj})
                plain_message = strip_tags(html_message)

                email = EmailMultiAlternatives(
                    subject=subject,
                    body=plain_message,
                    from_email="a.store.luxury.perfumes@gmail.com",
                    to=[to_email],
                    headers={
                        "Reply-To": "a.store.luxury.perfumes@gmail.com",
                        "X-Mailer": "Django",
                        "Message-ID": f"<{order_obj.id}-invoice@yourstore.com>",
                    },
                )
                email.attach_alternative(html_message, "text/html")
                email.send()
            except Exception as e:
                print(f"حدث خطأ أثناء إرسال الإيميل: {e}")

    if customer_email:
        email_thread = threading.Thread(target=send_invoice_email_bg, args=(order, customer_email))
        email_thread.start()

    if payment_method_input in ["card", "wallet", "instapay_paymob"]:
        if payment_method_input == "card":
            integration_id = getattr(settings, 'PAYMOB_CARD_INTEGRATION_ID', None)
        elif payment_method_input == "wallet":
            integration_id = getattr(settings, 'PAYMOB_WALLET_INTEGRATION_ID', None)
        elif payment_method_input == "instapay_paymob":
            integration_id = getattr(settings, 'PAYMOB_INSTAPAY_INTEGRATION_ID', getattr(settings, 'PAYMOB_WALLET_INTEGRATION_ID', None))

        payment_url = get_paymob_payment_url(order, integration_id, payment_method_input)

        if payment_url:
            cart.items.all().delete()
            if "cart" in request.session:
                del request.session["cart"]
                request.session.modified = True
            return redirect(payment_url)
        else:
            messages.error(request, _("حدث خطأ أثناء الاتصال ببوابة الدفع. يرجى المحاولة مرة أخرى."))
            return redirect("checkout")

    else:
        cart.items.all().delete()
        if "cart" in request.session:
            del request.session["cart"]
            request.session.modified = True

        return redirect("order_success", order_id=order.id)


@login_required
def buy_now(request, id):
    product = get_object_or_404(Product, id=id)
    size = request.GET.get("size", "50")

    cart, created = Cart.objects.get_or_create(user=request.user)
    cart_item, item_created = CartItem.objects.get_or_create(
        cart=cart,
        product=product,
        size=size,
        defaults={'quantity': 1}
    )

    if not item_created:
        cart_item.quantity += 1
        cart_item.save()

    checkout_url = reverse("checkout")
    return redirect(f"{checkout_url}?size={size}")


@login_required
def my_orders(request):
    orders = Order.objects.filter(user=request.user).order_by("-id")
    return render(request, "products/my_orders.html", {"orders": orders})


@login_required
def toggle_wishlist(request, id):
    product = get_object_or_404(Product, id=id)
    wishlist_item = Wishlist.objects.filter(user=request.user, product=product)

    if wishlist_item.exists():
        wishlist_item.delete()
    else:
        Wishlist.objects.create(user=request.user, product=product)

    return redirect(request.META.get("HTTP_REFERER", "user_product_list"))


@login_required
def wishlist_view(request):
    wishlist_items = Wishlist.objects.filter(user=request.user).order_by("-added_at")
    return render(request, "products/wishlist.html", {"wishlist_items": wishlist_items})


def paymob_callback(request):
    success = request.GET.get('success')
    merchant_order_id = request.GET.get('merchant_order_id')
    transaction_id = request.GET.get('id')

    if not merchant_order_id:
        return redirect('cart')

    try:
        order = Order.objects.get(id=merchant_order_id)
    except Order.DoesNotExist:
        return redirect('cart')

    if success == "true":
        order.payment_status = "paid"
        order.save()
        threading.Thread(target=update_payment_status_in_sheet, args=(order.id, "paid")).start()
        messages.success(request, _("🎉 تم الدفع بنجاح! رقم العملية: %(trans_id)s") % {'trans_id': transaction_id})
        return render(request, "products/order_success.html", {"order": order})
    else:
        messages.error(request, _("❌ فشلت عملية الدفع أو تم رفضها من البنك. يرجى المحاولة مرة أخرى أو اختيار الدفع عند الاستلام."))
        return redirect('checkout')


@login_required
def apply_coupon(request):
    if request.method == "POST":
        code = request.POST.get("coupon_code")
        try:
            coupon = Coupon.objects.get(code__iexact=code, active=True)
            request.session["coupon_id"] = coupon.id
        except Coupon.DoesNotExist:
            request.session["coupon_id"] = None
    return redirect("checkout")


# ==============================================================
# لوحة التحكم ومزامنة الشيت (Dashboard & Google Sheets)
# ==============================================================
@login_required
@user_passes_test(is_admin, login_url='user_product_list')
def dashboard_product_list(request):
    products = Product.objects.prefetch_related('accords', 'images').all()
    return render(request, "products/dashboard/dashboard_product_list.html", {"products": products})


@login_required
def dashboard_home(request):
    if not request.user.is_superuser:
        return redirect('home')

    today = timezone.localdate()
    total_orders = Order.objects.count()
    total_products = Product.objects.count()

    delivered_qs = Order.objects.filter(status='delivered')
    total_revenue = delivered_qs.aggregate(Sum('total_price'))['total_price__sum'] or 0

    total_net_profit = delivered_qs.aggregate(
        profit=Sum((F('items__price') - F('items__cost_price')) * F('items__quantity'))
    )['profit'] or 0

    today_orders_qs = Order.objects.filter(created_at__date=today)
    today_orders_count = today_orders_qs.count()

    today_delivered_qs = today_orders_qs.filter(status='delivered')
    today_revenue = today_delivered_qs.aggregate(Sum('total_price'))['total_price__sum'] or 0

    today_net_profit = today_delivered_qs.aggregate(
        profit=Sum((F('items__price') - F('items__cost_price')) * F('items__quantity'))
    )['profit'] or 0

    active_filter = request.GET.get('filter', 'all')
    base_qs = Order.objects.all()
    if active_filter == 'today':
        base_qs = today_orders_qs

    pending_orders = base_qs.filter(status='processing').order_by('-created_at')
    shipped_orders = base_qs.filter(status='shipped').order_by('-created_at')
    delivered_orders = base_qs.filter(status='delivered').order_by('-created_at')[:30]
    cancelled_orders = base_qs.filter(status='cancelled').order_by('-created_at')[:30]

    days = int(request.GET.get('days', 7))
    dates = []
    sales = []
    for i in range(days - 1, -1, -1):
        target_date = today - timedelta(days=i)
        dates.append(target_date.strftime("%d %b"))
        day_sales = Order.objects.filter(created_at__date=target_date, status='delivered').aggregate(Sum('total_price'))['total_price__sum'] or 0
        sales.append(float(day_sales))

    low_stock_products = Product.objects.filter(stock__lte=5).order_by('stock')

    context = {
        'total_orders': total_orders,
        'total_products': total_products,
        'total_revenue': total_revenue,
        'total_net_profit': total_net_profit,
        'today_orders_count': today_orders_count,
        'today_revenue': today_revenue,
        'today_net_profit': today_net_profit,
        'active_filter': active_filter,
        'dates': dates,
        'sales': sales,
        'selected_days': days,
        'pending_orders': pending_orders,
        'shipped_orders': shipped_orders,
        'delivered_orders': delivered_orders,
        'cancelled_orders': cancelled_orders,
        'low_stock_products': low_stock_products,
    }
    return render(request, 'products/dashboard/dashboard_home.html', context)


@login_required
def get_unread_notifications(request):
    if request.user.is_staff or request.user.is_superuser:
        notifications = Notification.objects.filter(is_read=False).select_related('order')
        data_list = []
        for n in notifications:
            data_list.append({
                "id": n.id,
                "order_id": n.order.id if n.order else 0,
                "customer_name": n.order.name if n.order else "عميل غير معروف",
                "total": str(n.order.total_price) if n.order else "0",
                "time_ago": timesince(n.created_at) + " مضت",
            })
        return JsonResponse({
            "count": notifications.count(),
            "notifications": data_list
        })
    return JsonResponse({"count": 0, "notifications": []})


@login_required
def dashboard_order_detail(request, id):
    if not request.user.is_superuser:
        return redirect('home')

    order = get_object_or_404(Order, id=id)
    if request.method == 'POST':
        payment_status = request.POST.get('payment_status')
        order_status = request.POST.get('status')
        tracking_number = request.POST.get('tracking_number')

        if payment_status:
            order.payment_status = payment_status
            threading.Thread(target=update_payment_status_in_sheet, args=(order.id, payment_status)).start()
        if order_status:
            order.status = order_status
            threading.Thread(target=update_order_status_in_sheet, args=(order.id, order_status)).start()
        if tracking_number is not None:
            order.tracking_number = tracking_number

        order.save()
        messages.success(request, 'تم تحديث حالة الطلب بنجاح!')
        return redirect('dashboard_order_detail', id=order.id)

    return render(request, 'products/dashboard/order_detail.html', {'order': order})


@user_passes_test(is_admin)
def add_product(request):
    form = ProductForm(request.POST or None, request.FILES or None)
    if form.is_valid():
        product = form.save()

        images = request.FILES.getlist('gallery')
        for img in images:
            ProductImage.objects.create(product=product, image=img)

        accord_names = request.POST.getlist('accord_name') or request.POST.getlist('accord_name[]')
        accord_names_en = request.POST.getlist('accord_name_en') or request.POST.getlist('accord_name_en[]')
        accord_percentages = request.POST.getlist('accord_percentage') or request.POST.getlist('accord_percentage[]')
        accord_colors = request.POST.getlist('accord_color') or request.POST.getlist('accord_color[]')

        for i in range(len(accord_names)):
            name = accord_names[i]
            percentage = accord_percentages[i]
            color = accord_colors[i]
            name_en = accord_names_en[i] if i < len(accord_names_en) else ""

            if name.strip() and percentage:
                ProductAccord.objects.create(
                    product=product,
                    name=name,
                    name_en=name_en,
                    percentage=percentage,
                    color_theme=color
                )

        return redirect("dashboard_product_list")

    return render(request, "products/add_product.html", {"form": form})


@user_passes_test(is_admin)
def update_product(request, id):
    product = get_object_or_404(Product, id=id)
    form = ProductForm(request.POST or None, request.FILES or None, instance=product)

    if form.is_valid():
        product = form.save()

        save_needed = False

        if request.POST.get('delete_image') == 'yes' and product.image:
            product.image.delete(save=False)
            product.image = None
            save_needed = True

        if request.POST.get('delete_image_2') == 'yes' and product.image_2:
            product.image_2.delete(save=False)
            product.image_2 = None
            save_needed = True

        if request.POST.get('delete_image_3') == 'yes' and product.image_3:
            product.image_3.delete(save=False)
            product.image_3 = None
            save_needed = True

        if save_needed:
            product.save()

        images_to_delete = request.POST.getlist('delete_gallery_images')
        if images_to_delete:
            ProductImage.objects.filter(id__in=images_to_delete).delete()

        images = request.FILES.getlist('gallery')
        for img in images:
            ProductImage.objects.create(product=product, image=img)

        accord_names = request.POST.getlist('accord_name') or request.POST.getlist('accord_name[]')
        accord_names_en = request.POST.getlist('accord_name_en') or request.POST.getlist('accord_name_en[]')
        accord_percentages = request.POST.getlist('accord_percentage') or request.POST.getlist('accord_percentage[]')
        accord_colors = request.POST.getlist('accord_color') or request.POST.getlist('accord_color[]')

        if hasattr(product, 'accords'):
            product.accords.all().delete()
        elif hasattr(product, 'productaccord_set'):
            product.productaccord_set.all().delete()

        for i in range(len(accord_names)):
            name = accord_names[i]
            percentage = accord_percentages[i]
            color = accord_colors[i]
            name_en = accord_names_en[i] if i < len(accord_names_en) else ""

            if name.strip() and percentage:
                ProductAccord.objects.create(
                    product=product,
                    name=name,
                    name_en=name_en,
                    percentage=percentage,
                    color_theme=color
                )

        return redirect("dashboard_product_list")

    return render(request, "products/update_product.html", {"form": form})


@user_passes_test(is_admin)
def delete_product(request, id):
    product = get_object_or_404(Product, id=id)
    product.delete()
    return redirect("dashboard_product_list")


def send_order_to_google_sheet(order):
    try:
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        json_file_name = os.getenv("GOOGLE_SHEET_CREDENTIALS")
        if not json_file_name:
            return
        key_path = os.path.join(settings.BASE_DIR, json_file_name)

        credentials = Credentials.from_service_account_file(key_path, scopes=scopes)
        client = gspread.authorize(credentials)

        sheet_id = "1osz169FsebIxb7TWyrZmome_7kFYwqD56vI2CbxH66w"
        sheet = client.open_by_key(sheet_id).sheet1

        items = OrderItem.objects.filter(order=order)
        products_details = "\n".join(
            [
                f"- {item.product.name} ({item.size}ML) | الكمية: {item.quantity}"
                for item in items
            ]
        )

        order_date = (
            localtime(order.created_at).strftime("%Y-%m-%d %I:%M %p")
            if hasattr(order, "created_at")
            else ""
        )

        row = [
            order.id,
            order.name,
            order.phone,
            order.get_city_display(),
            order.address,
            getattr(order, "status", "جاري التجهيز"),
            getattr(order, "payment_status", "قيد الانتظار"),
            float(order.shipping_cost),
            float(order.total_price),
            order.payment_method,
            getattr(order, "tracking_number", "") or "لا يوجد",
            order.payment_proof.url if getattr(order, "payment_proof", None) else "بدون صورة",
            order_date,
            products_details,
        ]

        sheet.append_row(row)
        print(f"✅ تم إرسال الطلب {order.id} لجوجل شيت بنجاح!")
    except Exception as e:
        print(f"❌ حدث خطأ أثناء إرسال البيانات لجوجل شيت: {e}")


def update_order_status_in_sheet(order_id, new_status):
    try:
        json_file_name = os.getenv("GOOGLE_SHEET_CREDENTIALS")
        if not json_file_name:
            return
        key_path = os.path.join(settings.BASE_DIR, json_file_name)

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        credentials = Credentials.from_service_account_file(key_path, scopes=scopes)
        client = gspread.authorize(credentials)

        sheet_id = "1osz169FsebIxb7TWyrZmome_7kFYwqD56vI2CbxH66w"
        sheet = client.open_by_key(sheet_id).sheet1

        order_ids_in_sheet = sheet.col_values(1)
        str_order_id = str(order_id)

        if str_order_id in order_ids_in_sheet:
            row_index = order_ids_in_sheet.index(str_order_id) + 1
            sheet.update_cell(row_index, 6, new_status)
    except Exception as e:
        print(f"❌ حدث خطأ أثناء تحديث حالة الطلب في الشيت: {e}")


def update_payment_status_in_sheet(order_id, new_payment_status):
    try:
        json_file_name = os.getenv("GOOGLE_SHEET_CREDENTIALS")
        if not json_file_name:
            return
        key_path = os.path.join(settings.BASE_DIR, json_file_name)

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        credentials = Credentials.from_service_account_file(key_path, scopes=scopes)
        client = gspread.authorize(credentials)

        sheet_id = "1osz169FsebIxb7TWyrZmome_7kFYwqD56vI2CbxH66w"
        sheet = client.open_by_key(sheet_id).sheet1

        order_ids_in_sheet = sheet.col_values(1)
        str_order_id = str(order_id)

        if str_order_id in order_ids_in_sheet:
            row_index = order_ids_in_sheet.index(str_order_id) + 1
            sheet.update_cell(row_index, 7, new_payment_status)
    except Exception as e:
        print(f"❌ حدث خطأ أثناء تحديث حالة الدفع في الشيت: {e}")


@user_passes_test(is_admin)
def export_orders_csv(request):
    response = HttpResponse(content_type="text/csv; charset=utf-8-sig")
    response["Content-Disposition"] = 'attachment; filename="orders_report.csv"'

    writer = csv.writer(response)
    writer.writerow([
        "رقم الطلب", "اسم العميل", "رقم الهاتف", "المدينة", "العنوان", "طريقة الدفع", "إجمالي السعر"
    ])

    orders = Order.objects.all().order_by("-id")
    for order in orders:
        writer.writerow([
            order.id, order.name, order.phone, order.get_city_display(),
            order.address, order.payment_method, order.total_price
        ])

    return response


@login_required
def dashboard_order_whatsapp(request, id):
    if not request.user.is_superuser and not request.user.is_staff:
        return redirect('dashboard_home')

    order = get_object_or_404(Order, id=id)
    items = order.items.all()

    products_text = "\n".join([f"- {item.product.name} ({item.size}ML) x {item.quantity}" for item in items])
    tracking_text = f"\n*رقم التتبع:* {order.tracking_number}" if order.tracking_number else ""

    city_name = order.get_city_display() if order.city else ""
    district_name = f" ({order.district})" if order.district else ""
    full_address = f"{city_name}{district_name} - {order.address}"

    try:
        invoice_url = request.build_absolute_uri(reverse('dashboard_order_print', args=[order.id]))
    except Exception:
        invoice_url = "رابط الفاتورة غير متاح"

    try:
        tracking_url = request.build_absolute_uri(reverse('my_orders'))
    except Exception:
        tracking_url = "رابط المتابعة غير متاح"

    message = f"""مرحباً أ. {order.name}
يسعدنا تأكيد تفاصيل طلبك من متجرنا.

*رقم الطلب:* #{order.id}
*العنوان:* {full_address}

*المنتجات المطلوبة:*
{products_text}

*الإجمالي النهائي:* {order.total_price} ج.م
*طريقة الدفع:* {order.get_payment_method_display()}{tracking_text}

*لعرض وتحميل فاتورة الطلب، تفضل بزيارة الرابط التالي:*
{invoice_url}

*لمتابعة حالة طلباتك خطوة بخطوة:*
{tracking_url}

سيتم التواصل معك قريباً لتسليم الطلب. شكراً لثقتك بنا!"""

    phone = str(order.phone).strip()
    if phone.startswith('01'):
        whatsapp_phone = '2' + phone
    elif phone.startswith('+'):
        whatsapp_phone = phone[1:]
    else:
        whatsapp_phone = phone

    context = {
        'order': order,
        'message': message,
        'whatsapp_phone': whatsapp_phone,
        'encoded_message': quote(message)
    }

    return render(request, 'products/dashboard/order_whatsapp.html', context)


@login_required
def dashboard_order_print(request, id):
    if not request.user.is_superuser:
        return redirect('home')
    order = get_object_or_404(Order, id=id)
    return render(request, 'admin/order_print.html', {'order': order})


@login_required
def dashboard_coupon_list(request):
    if not request.user.is_superuser:
        return redirect('home')
    coupons = Coupon.objects.all().order_by('-id')
    return render(request, 'products/dashboard/coupon_list.html', {'coupons': coupons})


@login_required
def dashboard_coupon_add(request):
    if not request.user.is_superuser:
        return redirect('home')

    if request.method == 'POST':
        form = CouponForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('dashboard_coupon_list')
    else:
        form = CouponForm()

    context = {'form': form, 'title': '➕ إضافة كود خصم جديد'}
    return render(request, 'products/dashboard/dashboard_form.html', context)


@login_required
def dashboard_coupon_update(request, id):
    if not request.user.is_superuser:
        return redirect('home')

    coupon = get_object_or_404(Coupon, id=id)
    if request.method == 'POST':
        form = CouponForm(request.POST, instance=coupon)
        if form.is_valid():
            form.save()
            return redirect('dashboard_coupon_list')
    else:
        form = CouponForm(instance=coupon)

    context = {'form': form, 'title': '✏️ تعديل كود الخصم'}
    return render(request, 'products/dashboard/dashboard_form.html', context)


@login_required
def dashboard_coupon_delete(request, id):
    if not request.user.is_superuser:
        return redirect('home')
    coupon = get_object_or_404(Coupon, id=id)
    coupon.delete()
    return redirect('dashboard_coupon_list')


@login_required
def toggle_coupon(request, id):
    if not request.user.is_superuser:
        return redirect('home')
    coupon = get_object_or_404(Coupon, id=id)
    coupon.active = not coupon.active
    coupon.save()
    return redirect('dashboard_coupon_list')


@login_required
def dashboard_customer_list(request):
    if not request.user.is_superuser:
        return redirect('home')
    customers = User.objects.annotate(order_count=Count('orders')).order_by('-date_joined')
    return render(request, 'products/dashboard/customer_list.html', {'customers': customers})


@login_required
def dashboard_review_list(request):
    if not request.user.is_superuser:
        return redirect('home')
    reviews = Review.objects.all().order_by('-created_at')
    return render(request, 'products/dashboard/review_list.html', {'reviews': reviews})


@login_required
def dashboard_review_delete(request, id):
    if not request.user.is_superuser:
        return redirect('home')
    review = get_object_or_404(Review, id=id)
    review.delete()
    return redirect('dashboard_review_list')


@login_required
def mark_notifications_as_read(request):
    if request.user.is_staff or request.user.is_superuser:
        Notification.objects.filter(is_read=False).update(is_read=True)
    return JsonResponse({"status": "success"})


@login_required
def dashboard_orders(request):
    if not request.user.is_superuser:
        return redirect('home')
    orders = Order.objects.select_related('user').prefetch_related('items__product').order_by('-created_at')
    return render(request, 'products/dashboard/dashboard_orders.html', {'orders': orders})


def order_success(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    return render(request, "products/order_success.html", {"order": order})