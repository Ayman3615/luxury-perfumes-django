from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from django.core.mail import send_mail
from products.models import Cart  # اسم التطبيق products وموديل السلة Cart

class Command(BaseCommand):
    help = 'إرسال إيميلات تذكيرية للعملاء الذين تركوا منتجات في السلة ولم يكملوا الشراء'

    def handle(self, *args, **kwargs):
        # تحديد المدة (السلات التي لم يتم تعديلها منذ 24 ساعة)
        time_threshold = timezone.now() - timedelta(hours=24)
        
        # جلب السلات المتروكة
        abandoned_carts = Cart.objects.filter(
            updated_at__lt=time_threshold,
            abandoned_email_sent=False
        )

        count = 0
        for cart in abandoned_carts:
            # التأكد أن السلة تحتوي على منتجات فعلاً عبر العلاقة
            if cart.items.exists(): 
                subject = '✨ نسيت عطرك المفضل في السلة؟'
                
                # معالجة اسم المستخدم بطريقة بايثون السليمة
                user_name = cart.user.first_name if cart.user.first_name else cart.user.username
                
                html_message = f"""
                <div dir="rtl" style="font-family: Arial, sans-serif; background: #111; color: #fff; padding: 30px; border-radius: 12px;">
                    <h2 style="color: #d4af37;">مرحباً {user_name}،</h2>
                    <p style="font-size: 16px; color: #ccc;">لاحظنا أنك تركت بعض العطور الساحرة في سلة المشتريات ولم تتابع إتمام الطلب.</p>
                    <p style="font-size: 16px; color: #ccc;">العطور الفاخرة تنفد سريعاً، أكمل طلبك الآن واقتنِ عطرك المميز!</p>
                    <div style="margin-top: 30px;">
                        <a href="https://yourdomain.com/cart/" style="background: #d4af37; color: #111; padding: 12px 25px; border-radius: 8px; text-decoration: none; font-weight: bold; display: inline-block;">أكمل طلبك الآن 🛒</a>
                    </div>
                </div>
                """
                
                try:
                    send_mail(
                        subject,
                        'عطورك الفاخرة لا تزال تنتظرك في السلة.',
                        'sales@yourdomain.com',
                        [cart.user.email],
                        html_message=html_message,
                        fail_silently=False,
                    )
                    
                    cart.abandoned_email_sent = True
                    cart.save()
                    count += 1
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'فشل إرسال إيميل لـ {cart.user.email}: {e}'))

        self.stdout.write(self.style.SUCCESS(f'تم إرسال {count} إيميل تذكيري بنجاح!'))