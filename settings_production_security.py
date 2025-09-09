# GreaterWMS 生产环境安全配置建议
# 生成时间: 2025-09-09 16:29:13

# 1. 基础安全设置
DEBUG = False  # 生产环境必须关闭DEBUG
ALLOWED_HOSTS = ['your-domain.com', 'www.your-domain.com']  # 限制允许的主机

# 2. 密钥安全
SECRET_KEY = 'your-new-secret-key-here'  # 请生成新的密钥

# 3. HTTPS安全设置
SECURE_SSL_REDIRECT = True  # 强制HTTPS重定向
SECURE_HSTS_SECONDS = 31536000  # HSTS设置（1年）
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True  # 防止MIME类型嗅探
SECURE_BROWSER_XSS_FILTER = True  # XSS过滤器

# 4. Cookie安全设置
SESSION_COOKIE_SECURE = True  # HTTPS环境下使用
SESSION_COOKIE_HTTPONLY = True  # 防止XSS攻击
SESSION_COOKIE_SAMESITE = 'Strict'  # CSRF保护
SESSION_EXPIRE_AT_BROWSER_CLOSE = True  # 浏览器关闭时清除会话

# 5. CSRF保护设置
CSRF_COOKIE_SECURE = True  # HTTPS环境下使用
CSRF_COOKIE_HTTPONLY = True  # 防止JavaScript访问
CSRF_COOKIE_SAMESITE = 'Strict'

# 6. 中间件配置（确保包含CSRF中间件）
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',  # 重要：CSRF保护
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# 7. 密码验证增强
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 12,  # 最小密码长度
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# 8. 日志安全设置
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'security_file': {
            'level': 'WARNING',
            'class': 'logging.FileHandler',
            'filename': 'logs/security.log',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django.security': {
            'handlers': ['security_file'],
            'level': 'WARNING',
            'propagate': True,
        },
    },
}

# 9. 数据库连接安全
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
        'OPTIONS': {
            'timeout': 20,
            # 对于生产环境，建议使用PostgreSQL或MySQL
        }
    }
}

# 10. 文件上传安全
FILE_UPLOAD_MAX_MEMORY_SIZE = 5242880  # 5MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 5242880  # 5MB
FILE_UPLOAD_PERMISSIONS = 0o644
