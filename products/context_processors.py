from .models import Cart

def cart_count(request):
    count = 0
    if request.user.is_authenticated:
        # لو مسجل، احسب عدد المنتجات من قاعدة البيانات
        try:
            cart = Cart.objects.get(user=request.user)
            # نجمع كل الكميات للمنتجات الموجودة في السلة
            count = sum(item.quantity for item in cart.items.all())
        except Cart.DoesNotExist:
            count = 0
    else:
        # لو زائر، احسب عدد المنتجات من الـ Session
        cart_session = request.session.get("cart", {})
        count = sum(cart_session.values())
        
    # نُرجع المتغير 'cart_count' ليكون متاحاً في كل ملفات الـ HTML
    return {'cart_count': count}