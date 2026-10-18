from pathlib import Path
import os
from dotenv import load_dotenv

# ===========================
# Base Directory
# ===========================
# 1. تحديد مسار المشروع الأساسي أولاً
BASE_DIR = Path(__file__).resolve().parent.parent

# ===========================
# Security
# ===========================
# 2. إخبار load_dotenv بالمسار الدقيق لملف .env
load_dotenv(os.path.join(BASE_DIR, ".env"))

# 3. سحب المفتاح السري الآن
SECRET_KEY = os.getenv("SECRET_KEY")

# إغلاق وضع التطوير للأمان
DEBUG = False

# تحديد النطاق المسموح به لمنع هجمات Host Header
ALLOWED_HOSTS = ['aymanshaban.pythonanywhere.com']

# 🔴 الحل الجذري لمشكلة 403 (Forbidden / CSRF)
CSRF_TRUSTED_ORIGINS = [
    'https://aymanshaban.pythonanywhere.com',
    'http://aymanshaban.pythonanywhere.com',
    'https://www.aymanshaban.pythonanywhere.com',
]

# ===========================
# Applications
# ===========================

INSTALLED_APPS = [
    "products",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]


# ===========================
# Middleware
# ===========================

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    # 🔴 LocaleMiddleware لدعم الترجمة واللغات (ar/en)
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


# ===========================
# URL Configuration
# ===========================

ROOT_URLCONF = "myproject.urls"


# ===========================
# Templates
# ===========================

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                # أضفنا هذا السطر لكي يعمل العداد في كل الصفحات
                "products.context_processors.cart_count",
            ],
        },
    },
]


WSGI_APPLICATION = "myproject.wsgi.application"


# ===========================
# Database
# ===========================

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}


# ===========================
# Password Validation
# ===========================

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# ===========================
# Internationalization
# ===========================

LANGUAGE_CODE = "ar"

# 🔴 اللغات المدعومة في المتجر
LANGUAGES = [
    ('ar', 'Arabic'),
    ('en', 'English'),
]

TIME_ZONE = "Africa/Cairo"

USE_I18N = True

USE_TZ = True

# 🔴 مسار ملفات الترجمة
LOCALE_PATHS = [
    BASE_DIR / 'locale',
]


# ===========================
# Static Files
# ===========================

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [
    BASE_DIR / "static",
]


# ===========================
# Media Files
# ===========================

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"


# ===========================
# Authentication
# ===========================

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "user_product_list"
LOGOUT_REDIRECT_URL = "login"


# ===========================
# Default Primary Key
# ===========================

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ==========================================
# 📧 إعدادات إرسال الفواتير عبر (Brevo SMTP)
# ==========================================
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp-relay.brevo.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True

EMAIL_HOST_USER = "b67b1d001@smtp-brevo.com"
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")


# ==========================================
# 💳 إعدادات بوابة الدفع (Paymob)
# ==========================================
PAYMOB_API_KEY = os.getenv("PAYMOB_API_KEY")

PAYMOB_CARD_INTEGRATION_ID = "5881742"  # الفيزا
PAYMOB_WALLET_INTEGRATION_ID = "5881978"  # المحافظ الإلكترونية

PAYMOB_CARD_IFRAME_ID = "1072062"
PAYMOB_WALLET_IFRAME_ID = "1072160"


# ==========================================
# 🤖 إعدادات الذكاء الاصطناعي (Gemini)
# ==========================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


# ==========================================
# 🔒 إعدادات الأمان والتشفير (Security & HTTPS)
# ==========================================
# السطر ده بيحل مشكلة CSRF على PythonAnywhere
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# فرض تحويل أي زائر لـ HTTPS بدلاً من HTTP
SECURE_SSL_REDIRECT = True

# تشفير ملفات تعريف الارتباط الخاصة بالجلسة
SESSION_COOKIE_SECURE = True

# تشفير توكن الحماية للنماذج
CSRF_COOKIE_SECURE = True

# تفعيل حماية HSTS لمنع الهجمات الوسيطة (التفعيل لمدة سنة)
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True


