from django.urls import path, include
from . import views

urlpatterns = [
    # ==========================
    # مسار الترجمة (الأساسي لتشغيل زر تغيير اللغة)
    # ==========================
    path('i18n/', include('django.conf.urls.i18n')),

    # ==========================
    # واجهة المستخدم (User/Shop)
    # ==========================
    path("", views.home, name="home"),  # 👈 الصفحة الرئيسية للموقع (Hero + أحدث العطور والأكثر مبيعاً)
    path("shop/", views.user_product_list, name="user_product_list"),  # 👈 صفحة المتجر الكاملة
    path("product/<int:id>/", views.product_detail, name="product_detail"),

    # ==========================
    # سلة المشتريات (Cart)
    # ==========================
    path("cart/", views.cart_view, name="cart"),
    path("cart/clear/", views.clear_cart, name="clear_cart"),
    path("add-to-cart/<int:id>/", views.add_to_cart, name="add_to_cart"),
    path("cart/increase/<str:cart_key>/", views.increase_cart, name="increase_cart"),
    path("cart/decrease/<str:cart_key>/", views.decrease_cart, name="decrease_cart"),
    path("cart/remove/<str:cart_key>/", views.remove_from_cart, name="remove_from_cart"),

    # ==========================
    # الدفع والطلبات (Checkout & Orders)
    # ==========================
    path("checkout/", views.checkout_view, name="checkout"),
    path("place-order/", views.place_order, name="place_order"),
    path("buy-now/<int:id>/", views.buy_now, name="buy_now"),
    path("my-orders/", views.my_orders, name="my_orders"),
    path('paymob-callback/', views.paymob_callback, name='paymob_callback'),
    path('order/success/<int:order_id>/', views.order_success, name='order_success'),

    # ==========================
    # المصادقة (Authentication)
    # ==========================
    path("login/", views.login_view, name="login"),
    path("register/", views.register_view, name="register"),
    path("logout/", views.logout_view, name="logout"),

    # ==========================================
    # 👑 روابط لوحة التحكم (Dashboard)
    # ==========================================
    path('dashboard/', views.dashboard_home, name='dashboard_home'),
    path('dashboard/products/', views.dashboard_product_list, name='dashboard_product_list'),
    path('dashboard/product/add/', views.add_product, name='add_product'),
    path('dashboard/product/update/<int:id>/', views.update_product, name='update_product'),
    path('dashboard/product/delete/<int:id>/', views.delete_product, name='delete_product'),
    path('dashboard/orders/export/', views.export_orders_csv, name='export_orders'),

    # تفاصيل الطلب والطباعة والواتساب
    path('dashboard/order/<int:id>/', views.dashboard_order_detail, name='dashboard_order_detail'),
    path('dashboard/order/<int:id>/whatsapp/', views.dashboard_order_whatsapp, name='dashboard_order_whatsapp'),
    path('dashboard/order/<int:id>/print/', views.dashboard_order_print, name='dashboard_order_print'),
    path('dashboard/orders/', views.dashboard_orders, name='dashboard_orders'),

    # 🎟️ إدارة الكوبونات في الداشبورد
    path('dashboard/coupons/', views.dashboard_coupon_list, name='dashboard_coupon_list'),
    path('dashboard/coupons/add/', views.dashboard_coupon_add, name='dashboard_coupon_add'),
    path('dashboard/coupons/update/<int:id>/', views.dashboard_coupon_update, name='dashboard_coupon_update'),
    path('dashboard/coupons/delete/<int:id>/', views.dashboard_coupon_delete, name='dashboard_coupon_delete'),
    path('dashboard/coupons/toggle/<int:id>/', views.toggle_coupon, name='toggle_coupon'),

    # 👥 إدارة العملاء والتقييمات في الداشبورد
    path('dashboard/customers/', views.dashboard_customer_list, name='dashboard_customer_list'),
    path('dashboard/reviews/', views.dashboard_review_list, name='dashboard_review_list'),
    path('dashboard/reviews/delete/<int:id>/', views.dashboard_review_delete, name='dashboard_review_delete'),

    # ==========================
    # المفضلة (Wishlist) & الكوبونات
    # ==========================
    path('wishlist/', views.wishlist_view, name='wishlist'),
    path('wishlist/toggle/<int:id>/', views.toggle_wishlist, name='toggle_wishlist'),
    path("apply-coupon/", views.apply_coupon, name="apply_coupon"),

    # ==========================
    # API الإشعارات اللحظية للأدمن
    # ==========================
    path('api/notifications/', views.get_unread_notifications, name='get_notifications'),
    path('api/notifications/mark-read/', views.mark_notifications_as_read, name='mark_notifications_read'),


    path('ai-finder/', views.ai_perfume_finder, name='ai_perfume_finder'),
    path('api/recommend-perfumes/', views.api_recommend_perfumes, name='api_recommend_perfumes'),


]





