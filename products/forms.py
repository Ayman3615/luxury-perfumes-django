from django import forms
from .models import Product, Review, UserProfile, Coupon

# ==========================================
# فورم المنتجات (تم إضافة أسعار الأحجام)
# ==========================================


# ==========================================
# فورم المنتجات (تم إضافة أسعار الأحجام + حقول الترجمة)
# ==========================================
class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        # 🔴 ضفنا هنا خانات الترجمة (name_en, description_en)
        fields = [
            "name", "name_en", "category",
            "price", "price_30", "price_50", "price_100",
            "cost_price", "cost_price_30", "cost_price_50", "cost_price_100",
            "stock", "description", "description_en", "image", "video",
            "is_bundle", "bundled_products"
        ]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "أدخل اسم المنتج بالعربي"}),
            "name_en": forms.TextInput(attrs={"placeholder": "الاسم بالإنجليزي (سيتم ملؤه تلقائياً)"}),

            "price": forms.NumberInput(attrs={"placeholder": "السعر الأساسي (للعميل)"}),
            "price_30": forms.NumberInput(attrs={"placeholder": "سعر بيع 30 مل"}),
            "price_50": forms.NumberInput(attrs={"placeholder": "سعر بيع 50 مل"}),
            "price_100": forms.NumberInput(attrs={"placeholder": "سعر بيع 100 مل"}),

            "cost_price": forms.NumberInput(attrs={"placeholder": "التكلفة الأساسية عليك (مخفي)"}),
            "cost_price_30": forms.NumberInput(attrs={"placeholder": "تكلفة 30 مل (مخفي)"}),
            "cost_price_50": forms.NumberInput(attrs={"placeholder": "تكلفة 50 مل (مخفي)"}),
            "cost_price_100": forms.NumberInput(attrs={"placeholder": "تكلفة 100 مل (مخفي)"}),

            "stock": forms.NumberInput(attrs={"placeholder": "الكمية المتاحة في المخزون"}),

            "description": forms.Textarea(attrs={"rows": 4, "placeholder": "اكتب وصفاً تفصيلياً للمنتج بالعربي"}),
            "description_en": forms.Textarea(attrs={"rows": 4, "placeholder": "الوصف بالإنجليزي (سيتم ملؤه تلقائياً)"}),

            "image": forms.ClearableFileInput(),
            "video": forms.ClearableFileInput(),

            "is_bundle": forms.CheckboxInput(attrs={"style": "width: 20px; height: 20px; accent-color: var(--gold);"}),
            "bundled_products": forms.SelectMultiple(attrs={
                "style": "height: 150px; padding: 10px;",
                "title": "اضغط على Ctrl (أو Command) لاختيار أكثر من عطر"
            }),
        }

# (باقي الفورمز زي ReviewForm و UserProfileForm زي ما هي بدون تعديل)
# ==========================================
# فورم التقييمات
# ==========================================
class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ["rating", "comment"]
        labels = {
            "rating": "التقييم (من 1 إلى 5)",
            "comment": "رأيك في العطر",
        }
        widgets = {
            "comment": forms.Textarea(
                attrs={
                    "rows": 3,
                    "style": "width: 100%; padding: 10px; border-radius: 8px;",
                }
            ),
            "rating": forms.Select(
                attrs={"style": "padding: 5px; border-radius: 5px;"}
            ),
        }

# ==========================================
# فورم تعديل الملف الشخصي للعميل
# ==========================================
class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['phone', 'city', 'address']

        widgets = {
            'phone': forms.TextInput(attrs={'style': 'width: 100%; padding: 10px; margin-bottom: 15px; border-radius: 8px; border: 1px solid #ccc;', 'placeholder': 'رقم الهاتف'}),
            'city': forms.Select(attrs={'style': 'width: 100%; padding: 10px; margin-bottom: 15px; border-radius: 8px; border: 1px solid #ccc;'}),
            'address': forms.Textarea(attrs={'style': 'width: 100%; padding: 10px; margin-bottom: 15px; border-radius: 8px; border: 1px solid #ccc;', 'rows': 3, 'placeholder': 'العنوان بالتفصيل'}),
        }

# ==========================================
# 🔴 فورم الكوبونات الجديد (للوحة التحكم)
# ==========================================
class CouponForm(forms.ModelForm):
    class Meta:
        model = Coupon
        fields = ['code', 'discount', 'active', 'valid_until']
        labels = {
            'code': 'كود الخصم',
            'discount': 'نسبة الخصم (%)',
            'active': 'تفعيل الكوبون',
            'valid_until': 'تاريخ ووقت الانتهاء (اختياري)',
        }
        widgets = {
            # ده هيطلعلك نتيجة (نتيجة تقويم) تختار منها اليوم والساعة اللي هيقف فيها الكوبون!
            'valid_until': forms.DateTimeInput(attrs={'type': 'datetime-local', 'style': 'width: 100%; padding: 12px; background: #111; border: 1px solid #333; border-radius: 8px; color: white;'}),
        }