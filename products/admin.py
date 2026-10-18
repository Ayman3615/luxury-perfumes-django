from django.contrib import admin
from django.utils.html import format_html
from .models import Order, OrderItem, Product, ProductImage, Review
from .views import update_order_status_in_sheet
from .models import Coupon

admin.site.register(Coupon)
from django.urls import path
from django.shortcuts import get_object_or_404, render
from django.utils.safestring import mark_safe

# =========================
# Admin Site Settings
# =========================
admin.site.site_header = "Luxury Perfume Store"
admin.site.site_title = "Perfume Admin"
admin.site.index_title = "Welcome to Perfume Dashboard"


# =========================
# Product Images Inline
# =========================
class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 3  # عدد خانات صور جاهزة للإضافة


# =========================
# Product Admin
# =========================
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "price",
        "stock",
        "main_image_preview",
    )

    # ميزة رائعة: تتيح لك تعديل السعر والمخزون مباشرة من الجدول الخارجي
    list_editable = ("price", "stock")

    search_fields = ("name",)
    list_filter = ("stock",)

    # تحويل الأقواس لـ Tuple لتجنب تنبيه RUF012
    inlines = (ProductImageInline,)

    # عرض الصورة الرئيسية داخل الجدول
    def main_image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" width="60" style="border-radius:6px; object-fit:cover;" />',
                obj.image.url,
            )
        return "No Image"

    main_image_preview.short_description = "Image"


# =========================
# Order Item Inline
# =========================
# هذه الإضافة تجعلك ترى المنتجات المطلوبة داخل صفحة الطلب نفسها
class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0  # لا تقم بإضافة خانات فارغة

    # 🔴 ضفنا "size" هنا عشان يظهر في الأعمدة ويكون للقراءة فقط 🔴
    readonly_fields = ("product", "size", "quantity", "price", "item_total")
    fields = (
        "product",
        "size",
        "quantity",
        "price",
        "item_total",
    )  # لترتيب شكل الأعمدة

    can_delete = False

    def item_total(self, obj):
        return obj.total_cost  # الخاصية التي أضفناها في models.py

    item_total.short_description = "الإجمالي"


# =========================
# Order Admin
# =========================
@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "get_products_with_sizes",
        "status",
        "payment_status",
        "shipping_cost",
        "total_price",
        "payment_method",
        "tracking_number",
        "proof_image",
        "created_at",
    )

    def get_products_with_sizes(self, obj):
        items = obj.items.all()
        products_list = [f"{item.product.name} ({item.size}ML) x{item.quantity}" for item in items]
        return " | ".join(products_list)
    
    get_products_with_sizes.short_description = "المنتجات (بالأحجام)"

    list_editable = ("status", "payment_status", "tracking_number")
    list_filter = ("status", "payment_status", "payment_method", "created_at")
    search_fields = ("name", "phone", "tracking_number", "id")
    ordering = ("-created_at",)
    inlines = (OrderItemInline,)

    readonly_fields = ("proof_image", "total_price", "shipping_cost", "admin_actions_buttons")

    class Media:
        js = ('js/auto_refresh.js',)

    def proof_image(self, obj):
        if obj.payment_proof:
            return format_html(
                '<a href="{0}" target="_blank"><img src="{0}" width="80" style="border-radius:8px;" /></a>',
                obj.payment_proof.url,
            )
        return "No Image"
    
    proof_image.short_description = "Payment Proof"

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if change:
            arabic_status = obj.get_status_display()
            update_order_status_in_sheet(obj.id, arabic_status)

    # ==========================================
    # الإجراءات السريعة (واتساب وطباعة)
    # ==========================================
    def admin_actions_buttons(self, obj):
        if not obj.pk:
            return "متاح بعد حفظ الطلب"
        return mark_safe(
            '''
            <a href="../whatsapp-msg/" target="_blank" style="background: #25d366; color: white; padding: 10px 20px; border-radius: 5px; margin-right: 10px; text-decoration: none; font-weight: bold; font-size: 14px;">💬 تجهيز رسالة الواتساب</a>
            <a href="../print-invoice/" target="_blank" style="background: #007bff; color: white; padding: 10px 20px; border-radius: 5px; text-decoration: none; font-weight: bold; font-size: 14px;">🖨️ طباعة الفاتورة</a>
            '''
        )
    
    admin_actions_buttons.short_description = "إجراءات سريعة"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:object_id>/whatsapp-msg/',
                self.admin_site.admin_view(self.whatsapp_message_view),
                name='order-whatsapp-msg',
            ),
            path(
                '<int:object_id>/print-invoice/',
                self.admin_site.admin_view(self.print_invoice_view),
                name='order-print-invoice',
            ),
        ]
        return custom_urls + urls


    def whatsapp_message_view(self, request, object_id):
        order = get_object_or_404(Order, pk=object_id)
        items = order.items.all()
        products_text = "\n".join([f"▫️ {item.product.name} ({item.size}ML) x {item.quantity}" for item in items])
        
        message = f"""📦 *طلب جديد رقم: #{order.id}*
👤 *الاسم:* {order.name}
📞 *الهاتف:* {order.phone}
🏙️ *المحافظة:* {order.get_city_display()}
📍 *العنوان:* {order.address}

🛒 *المنتجات المطلوبة:*
{products_text}

💰 *الإجمالي النهائي:* {order.total_price} ج.م
💳 *طريقة الدفع:* {order.get_payment_method_display()}
"""
        # ==========================================
        # 🔴 الكود الجديد: تظبيط رقم الهاتف عشان واتساب
        # ==========================================
        phone = str(order.phone).strip()
        if phone.startswith('01'):
            whatsapp_phone = '2' + phone
        elif phone.startswith('+'):
            whatsapp_phone = phone[1:]
        else:
            whatsapp_phone = phone

        context = {
            **self.admin_site.each_context(request), 
            'order': order, 
            'message': message,
            'whatsapp_phone': whatsapp_phone  
        }
        return render(request, 'admin/order_whatsapp.html', context)

    # ==========================================
    # 🔴 دالة الطباعة اللي كانت ناقصة (حطيتها لك هنا)
    # ==========================================
    def print_invoice_view(self, request, object_id):
        order = get_object_or_404(Order, pk=object_id)
        context = {**self.admin_site.each_context(request), 'order': order}
        return render(request, 'admin/order_print.html', context)


# =========================
# تسجيل الموديلات الإضافية
# =========================
admin.site.register(Review)

   