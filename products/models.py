import os
import uuid
from io import BytesIO
from decimal import Decimal

from PIL import Image
from deep_translator import GoogleTranslator

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.db.models.signals import post_delete, post_save , pre_save
from django.dispatch import receiver
from django.utils.translation import get_language, gettext_lazy as _




# ==========================================
# ⚡ دالة تحويل وضغط الصور تلقائياً إلى WebP
# ==========================================
def compress_to_webp(image_field, max_width=1200, quality=82):
    """
    تحويل أي صورة مرفوعة إلى صيغة WebP وضغط مساحتها بنسبة 70% مع الحفاظ على الشفافية والجودة
    """
    if not image_field:
        return

    # إذا كانت الصورة بصيغة webp بالفعل لا نعيد تحويلها لتجنب تكرار الضغط عند تعديل المنتج
    if image_field.name.lower().endswith('.webp'):
        return

    try:
        img = Image.open(image_field)

        # الحفاظ على الشفافية للصور المفرغة (PNG/RGBA) وتحويل الباقي إلى RGB
        if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
            img = img.convert('RGBA')
        else:
            img = img.convert('RGB')

        # تصغير الأبعاد الضخمة جداً مع الحفاظ على التناسب
        if img.width > max_width or img.height > max_width:
            img.thumbnail((max_width, max_width), Image.Resampling.LANCZOS)

        # حفظ الصورة في الذاكرة المؤقتة بصيغة WebP
        output = BytesIO()
        img.save(output, format='WEBP', quality=quality, optimize=True)
        output.seek(0)

        # استبدال الامتداد القديم بـ .webp
        base_name = os.path.splitext(os.path.basename(image_field.name))[0]
        new_name = f"{base_name}.webp"

        # حفظ الملف الجديد مكان القديم بدون عمل save متكرر للداتابيز
        image_field.save(new_name, ContentFile(output.read()), save=False)
    except Exception as e:
        print(f"WebP Conversion Error: {e}")


# ==========================================
# 🧴 موديل المنتج الأساسي (Product)
# ==========================================
class Product(models.Model):
    CATEGORY_CHOICES = [  # noqa: RUF012
        ("men", "رجالي"),
        ("women", "نسائي"),
        ("unisex", "للجنسين"),
    ]
    category = models.CharField(
        max_length=20, choices=CATEGORY_CHOICES, default="unisex"
    )

    name = models.CharField(max_length=100)
    name_en = models.CharField(max_length=100, blank=True, null=True, verbose_name="الاسم بالإنجليزي")

    description = models.TextField()
    description_en = models.TextField(blank=True, null=True, verbose_name="الوصف بالإنجليزي")

    # 🟢 أسعار البيع للعميل
    price = models.DecimalField(max_digits=10, decimal_places=2)
    price_30 = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="سعر حجم 30 مل")
    price_50 = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="سعر حجم 50 مل")
    price_100 = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="سعر حجم 100 مل")

    # 🔴 أسعار التكلفة (للتاجر)
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="تكلفة الحجم الأساسي")
    cost_price_30 = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="تكلفة حجم 30 مل")
    cost_price_50 = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="تكلفة حجم 50 مل")
    cost_price_100 = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="تكلفة حجم 100 مل")

    # الميديا والمخزون
    image = models.ImageField(upload_to="products/", blank=True, null=True)
    video = models.FileField(upload_to="products/videos/", blank=True, null=True, verbose_name="فيديو المنتج")
    stock = models.PositiveIntegerField(default=0)

    # 🎁 نظام الباقات المجمعة (Bundles)
    is_bundle = models.BooleanField(default=False, verbose_name="هل هذا المنتج عبارة عن باقة مجمعة؟")
    bundled_products = models.ManyToManyField(
        'self',
        blank=True,
        symmetrical=False,
        verbose_name="العطور الموجودة داخل الباقة"
    )

    def save(self, *args, **kwargs):
        # 1. تحويل الصورة تلقائياً إلى WebP وضغط حجمها
        if self.image:
            compress_to_webp(self.image)

        # 2. الترجمة التلقائية للاسم والوصف إذا كانت الحقول الإنجليزية فارغة
        if (self.name and not self.name_en) or (self.description and not self.description_en):
            try:
                translator = GoogleTranslator(source='ar', target='en')
                if self.name and not self.name_en:
                    self.name_en = translator.translate(self.name)
                if self.description and not self.description_en:
                    self.description_en = translator.translate(self.description)
            except Exception as e:
                print(f"Error translating product: {e}")

        super().save(*args, **kwargs)

    @property
    def translated_name(self):
        lang = get_language() or 'ar'
        if str(lang).startswith('en') and self.name_en:
            return self.name_en
        return self.name

    @property
    def translated_description(self):
        lang = get_language() or 'ar'
        if str(lang).startswith('en') and self.description_en:
            return self.description_en
        return self.description

    def __str__(self):
        return self.name


# ==========================================
# 🖼️ صور إضافية للمنتج (Gallery)
# ==========================================
class ProductImage(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="images"
    )
    image = models.ImageField(upload_to="products/gallery/")

    def save(self, *args, **kwargs):
        # تحويل صور المعرض الإضافية تلقائياً إلى WebP
        if self.image:
            compress_to_webp(self.image)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Image for {self.product.name}"


# ==========================================
# 🌿 النوتات العطرية (Product Accords)
# ==========================================
class ProductAccord(models.Model):
    product = models.ForeignKey(Product, related_name='accords', on_delete=models.CASCADE)
    name = models.CharField(max_length=50, verbose_name="اسم النوتة (مثل: أخشاب عطرية)")
    name_en = models.CharField(max_length=50, blank=True, null=True, verbose_name="اسم النوتة بالإنجليزي")
    percentage = models.IntegerField(verbose_name="نسبة التركيز (من 10 إلى 100)")
    color_theme = models.CharField(max_length=20, default='#d4af37', verbose_name="كود اللون (Hex)")

    class Meta:
        ordering = ['-percentage']

    def save(self, *args, **kwargs):
        if self.name and not self.name_en:
            try:
                self.name_en = GoogleTranslator(source='ar', target='en').translate(self.name)
            except Exception as e:
                print(f"Error translating accord: {e}")
        super().save(*args, **kwargs)

    @property
    def translated_name(self):
        lang = get_language() or 'ar'
        if str(lang).startswith('en') and self.name_en:
            return self.name_en
        return self.name

    def __str__(self):
        return f"{self.name} - {self.product.name}"


# ==========================================
# 📦 الطلبات (Orders)
# ==========================================
class Order(models.Model):
    PAYMENT_CHOICES = [  # noqa: RUF012
        ("cash", "الدفع عند الاستلام"),
        ("vodafone", "Vodafone Cash"),
        ("instapay", "InstaPay"),
        ("instapay_manual", "InstaPay (تحويل يدوي)"),
        ("instapay_paymob", "InstaPay (دفع إلكتروني)"),
        ("card", "بطاقة بنكية (Visa / MasterCard)"),
        ("wallet", "محفظة إلكترونية"),
    ]

    PAYMENT_STATUS = [  # noqa: RUF012
        ("pending", "قيد الانتظار"),
        ("paid", "تم الدفع"),
        ("approved", "مقبول"),
        ("rejected", "مرفوض"),
    ]

    ORDER_STATUS = [  # noqa: RUF012
        ('under_review', 'تحت المراجعة'),
        ('reviewed', 'تم مراجعة الطلب'),
        ("processing", "جاري التجهيز"),
        ("shipped", "تم الشحن"),
        ("delivered", "تم التوصيل"),
        ("cancelled", "ملغي"),
    ]

    GOVERNORATE_CHOICES = [  # noqa: RUF012
        ("qalyubia", "القليوبية"),
        ("cairo", "القاهرة"), ("giza", "الجيزة"), ("alexandria", "الإسكندرية"),
        ("sharqia", "الشرقية"), ("monufia", "المنوفية"), ("gharbia", "الغربية"),
        ("dakahlia", "الدقهلية"), ("port_said", "بورسعيد"), ("suez", "السويس"),
        ("ismailia", "الإسماعيلية"), ("damietta", "دمياط"), ("kafr_el_sheikh", "كفر الشيخ"),
        ("beheira", "البحيرة"),
        ("fayoum", "الفيوم"), ("beni_suef", "بني سويف"), ("minya", "المنيا"),
        ("assiut", "أسيوط"), ("sohag", "سوهاج"), ("qena", "قنا"),
        ("luxor", "الأقصر"), ("aswan", "أسوان"),
        ("red_sea", "البحر الأحمر"), ("matrouh", "مطروح"), ("new_valley", "الوادي الجديد"),
        ("north_sinai", "شمال سيناء"), ("south_sinai", "جنوب سيناء"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="orders")
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    city = models.CharField(max_length=50, choices=GOVERNORATE_CHOICES, default="cairo")
    address = models.TextField()
    district = models.CharField(max_length=150, null=True, blank=True, verbose_name="المدينة / المركز")

    payment_method = models.CharField(max_length=20, choices=PAYMENT_CHOICES, default="cash")
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default="pending")
    status = models.CharField(max_length=20, choices=ORDER_STATUS, default="processing")

    payment_proof = models.ImageField(upload_to="payment_proofs/", blank=True, null=True)
    shipping_cost = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tracking_number = models.CharField(max_length=50, blank=True, null=True, unique=True, verbose_name="رقم التتبع")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    stock_updated = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]  # noqa: RUF012

    def __str__(self):
        return f"Order #{self.id} - {self.name}"

    @property
    def net_profit(self):
        return sum(item.profit for item in self.items.all())

    def save(self, *args, **kwargs):
        # 1. ضغط صورة إيصال الدفع إلى WebP لتوفير المساحة (إن وجدت)
        if self.payment_proof:
            compress_to_webp(self.payment_proof, max_width=1000, quality=80)

        # 2. تحديد سعر الشحن بناءً على المحافظة
        if self.city == "qalyubia":
            self.shipping_cost = 40
        elif self.city in ["cairo", "giza", "alexandria", "sharqia", "monufia", "gharbia", "dakahlia", "port_said", "suez", "ismailia", "damietta", "kafr_el_sheikh", "beheira"]:
            self.shipping_cost = 55
        elif self.city in ["fayoum", "beni_suef", "minya", "assiut", "sohag", "qena", "luxor", "aswan"]:
            self.shipping_cost = 75
        elif self.city in ["red_sea", "matrouh", "new_valley", "north_sinai", "south_sinai"]:
            self.shipping_cost = 95
        else:
            self.shipping_cost = 0

        # 3. إنشاء رقم تتبع أوتوماتيكي
        if not self.tracking_number:
            random_code = uuid.uuid4().hex[:8].upper()
            self.tracking_number = f"TRK-{random_code}"

        # 4. حفظ الأوردر في قاعدة البيانات
        super().save(*args, **kwargs)

        # 5. نظام الاسترجاع الأوتوماتيكي للمخزون عند الإلغاء
        if self.status == 'cancelled' and self.stock_updated:
            for item in self.items.all():
                item.product.stock += item.quantity
                item.product.save()

            Order.objects.filter(id=self.id).update(stock_updated=False)


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    size = models.CharField(max_length=20, null=True, blank=True, verbose_name="الحجم")
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="التكلفة وقت الشراء")

    @property
    def total_cost(self):
        if self.price is None or self.quantity is None:
            return Decimal("0.00")
        return self.price * self.quantity

    @property
    def profit(self):
        if self.price is not None and self.cost_price is not None and self.quantity is not None:
            return (self.price - self.cost_price) * self.quantity
        return Decimal("0.00")

    def __str__(self):
        return f"{self.product.name} ({self.size}ML) x {self.quantity}"


@receiver(post_save, sender=OrderItem)
@receiver(post_delete, sender=OrderItem)
def update_order_total(sender, instance, **kwargs):
    order = instance.order
    # إذا كان الطلب قد تم تأكيده وحساب خصمه بالفعل في place_order (stock_updated=True)
    # لا نلغي خصم الكوبون إلا لو تم تعديل العناصر يدوياً
    if not order.stock_updated:
        items_total = sum(item.total_cost for item in order.items.all())
        Order.objects.filter(id=order.id).update(
            total_price=Decimal(str(items_total)) + Decimal(str(order.shipping_cost))
        )


# ==========================================
# ⭐ التقييمات (Reviews)
# ==========================================
class Review(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="reviews"
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.IntegerField(
        choices=[(i, str(i)) for i in range(1, 6)]
    )
    comment = models.TextField()
    comment_en = models.TextField(blank=True, null=True, verbose_name="التعليق بالإنجليزي")
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.comment and not self.comment_en:
            try:
                translator = GoogleTranslator(source='ar', target='en')
                self.comment_en = translator.translate(self.comment)
            except Exception as e:
                print(f"Error translating review: {e}")
        super().save(*args, **kwargs)

    @property
    def translated_comment(self):
        lang = get_language() or 'ar'
        if str(lang).startswith('en') and self.comment_en:
            return self.comment_en
        return self.comment

    def __str__(self):
        return f"{self.user.username} - {self.product.name} - {self.rating} Stars"


# ==========================================
# ❤️ المفضلة والكوبونات والملف الشخصي والسلة
# ==========================================
class Wishlist(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='wishlist')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'product')

    def __str__(self):
        return f"{self.user.username} - {self.product.name}"


class Coupon(models.Model):
    code = models.CharField(max_length=50, unique=True, verbose_name="كود الخصم")
    discount = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(100)], verbose_name="نسبة الخصم (%)")
    active = models.BooleanField(default=True, verbose_name="مفعل")
    valid_until = models.DateTimeField(null=True, blank=True, verbose_name="تاريخ ووقت الانتهاء")

    def __str__(self):
        return f"{self.code} - {self.discount}%"


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name="رقم الهاتف")
    city = models.CharField(max_length=50, choices=Order.GOVERNORATE_CHOICES, default="cairo", verbose_name="المحافظة")
    address = models.TextField(blank=True, null=True, verbose_name="العنوان بالتفصيل")

    def __str__(self):
        return f"Profile for {self.user.username}"


class Cart(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='cart')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    abandoned_email_sent = models.BooleanField(default=False)

    def __str__(self):
        return f"Cart for {self.user.username}"


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    size = models.CharField(max_length=20, default="50", verbose_name="الحجم")

    @property
    def total_cost(self):
        if self.size == "30" and self.product.price_30:
            price = self.product.price_30
        elif self.size == "50" and self.product.price_50:
            price = self.product.price_50
        elif self.size == "100" and self.product.price_100:
            price = self.product.price_100
        else:
            price = self.product.price

        return price * self.quantity

    def __str__(self):
        return f"{self.product.name} ({self.size}ML) x {self.quantity}"


class Notification(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="notifications")
    message = models.CharField(max_length=255)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.message




@receiver(post_delete, sender=Product)
def auto_delete_file_on_delete(sender, instance, **kwargs):
    if instance.image and os.path.isfile(instance.image.path):
        os.remove(instance.image.path)

@receiver(pre_save, sender=Product)
def auto_delete_file_on_change(sender, instance, **kwargs):
    if not instance.pk:
        return False
    try:
        old_file = Product.objects.get(pk=instance.pk).image
    except Product.DoesNotExist:
        return False
    new_file = instance.image
    if old_file and old_file != new_file:
        if os.path.isfile(old_file.path):
            os.remove(old_file.path)



