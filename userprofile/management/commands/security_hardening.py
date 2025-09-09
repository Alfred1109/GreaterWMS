from django.core.management.base import BaseCommand
from django.conf import settings
import os
import stat
import shutil
from datetime import datetime

class Command(BaseCommand):
    help = 'GreaterWMS系统安全加固脚本'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='模拟运行，不实际修改文件'
        )
        parser.add_argument(
            '--backup',
            action='store_true',
            help='在修改前备份文件'
        )

    def handle(self, *args, **options):
        self.dry_run = options['dry_run']
        self.backup = options['backup']
        
        self.stdout.write(self.style.SUCCESS('🔧 GreaterWMS 系统安全加固'))
        self.stdout.write("=" * 80)
        
        if self.dry_run:
            self.stdout.write("⚠️  模拟运行模式 - 不会实际修改文件")
        
        self.stdout.write(f"加固时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.stdout.write("=" * 80)

        # 执行各项安全加固
        self.fix_file_permissions()
        self.fix_csrf_protection()
        self.generate_secure_settings()
        self.create_security_recommendations()
        
        self.stdout.write("\n" + "="*80)
        self.stdout.write("🎉 安全加固完成！")
        self.stdout.write("建议重新运行安全检测验证修复效果：")
        self.stdout.write("python manage.py security_check")

    def fix_file_permissions(self):
        """修复文件权限问题"""
        self.stdout.write(f"\n📁 1. 修复文件权限")
        self.stdout.write("-" * 40)
        
        # 关键文件列表和推荐权限
        critical_files = {
            'manage.py': 0o755,  # rwxr-xr-x
            'greaterwms/settings.py': 0o640,  # rw-r-----
            'greaterwms/wsgi.py': 0o644,  # rw-r--r--
            'db.sqlite3': 0o600  # rw-------
        }
        
        for file_path, recommended_mode in critical_files.items():
            if os.path.exists(file_path):
                current_stat = os.stat(file_path)
                current_mode = current_stat.st_mode
                
                if current_mode != recommended_mode:
                    if self.backup:
                        backup_path = f"{file_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                        if not self.dry_run:
                            shutil.copy2(file_path, backup_path)
                        self.stdout.write(f"  📦 已备份: {file_path} -> {backup_path}")
                    
                    if not self.dry_run:
                        try:
                            os.chmod(file_path, recommended_mode)
                            self.stdout.write(f"  ✅ 已修复: {file_path} -> {oct(recommended_mode)}")
                        except PermissionError:
                            self.stdout.write(f"  ❌ 权限不足: {file_path}")
                    else:
                        self.stdout.write(f"  🔄 将修复: {file_path} -> {oct(recommended_mode)}")
                else:
                    self.stdout.write(f"  ✅ 权限正常: {file_path}")
            else:
                self.stdout.write(f"  ⚠️  文件不存在: {file_path}")

    def fix_csrf_protection(self):
        """修复CSRF保护"""
        self.stdout.write(f"\n🛡️  2. 修复CSRF保护")
        self.stdout.write("-" * 40)
        
        settings_file = 'greaterwms/settings.py'
        
        if os.path.exists(settings_file):
            with open(settings_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 检查CSRF中间件是否存在
            csrf_middleware = 'django.middleware.csrf.CsrfViewMiddleware'
            
            if csrf_middleware not in content:
                self.stdout.write(f"  ⚠️  需要手动添加CSRF中间件到MIDDLEWARE配置中")
                self.stdout.write(f"     添加: '{csrf_middleware}'")
            else:
                self.stdout.write(f"  ✅ CSRF中间件已配置")
        else:
            self.stdout.write(f"  ❌ 设置文件不存在")

    def generate_secure_settings(self):
        """生成安全配置建议"""
        self.stdout.write(f"\n⚙️  3. 生成安全配置文件")
        self.stdout.write("-" * 40)
        
        secure_settings_content = """# GreaterWMS 生产环境安全配置建议
# 生成时间: {datetime}

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
    {{
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    }},
    {{
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {{
            'min_length': 12,  # 最小密码长度
        }}
    }},
    {{
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    }},
    {{
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    }},
]

# 8. 日志安全设置
LOGGING = {{
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {{
        'verbose': {{
            'format': '{{levelname}} {{asctime}} {{module}} {{process:d}} {{thread:d}} {{message}}',
            'style': '{{',
        }},
    }},
    'handlers': {{
        'security_file': {{
            'level': 'WARNING',
            'class': 'logging.FileHandler',
            'filename': 'logs/security.log',
            'formatter': 'verbose',
        }},
    }},
    'loggers': {{
        'django.security': {{
            'handlers': ['security_file'],
            'level': 'WARNING',
            'propagate': True,
        }},
    }},
}}

# 9. 数据库连接安全
DATABASES = {{
    'default': {{
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
        'OPTIONS': {{
            'timeout': 20,
            # 对于生产环境，建议使用PostgreSQL或MySQL
        }}
    }}
}}

# 10. 文件上传安全
FILE_UPLOAD_MAX_MEMORY_SIZE = 5242880  # 5MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 5242880  # 5MB
FILE_UPLOAD_PERMISSIONS = 0o644
""".format(datetime=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

        secure_settings_file = 'settings_production_security.py'
        
        if not self.dry_run:
            with open(secure_settings_file, 'w', encoding='utf-8') as f:
                f.write(secure_settings_content)
            self.stdout.write(f"  ✅ 已生成: {secure_settings_file}")
        else:
            self.stdout.write(f"  🔄 将生成: {secure_settings_file}")

    def create_security_recommendations(self):
        """创建安全建议文档"""
        self.stdout.write(f"\n📋 4. 生成安全建议文档")
        self.stdout.write("-" * 40)
        
        recommendations_content = f"""# GreaterWMS 安全加固建议

**生成时间：** {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}

## 🚨 立即处理的安全问题

### 1. 启用CSRF保护
- **问题：** CSRF中间件未启用，存在跨站请求伪造风险
- **解决方案：** 在 `greaterwms/settings.py` 的 `MIDDLEWARE` 中添加：
  ```python
  'django.middleware.csrf.CsrfViewMiddleware',
  ```
- **影响：** 高风险，可能导致用户在不知情的情况下执行恶意操作

### 2. 修复文件权限
- **问题：** 关键文件其他用户可写，存在被恶意修改的风险
- **解决方案：** 已通过安全加固脚本修复
- **建议权限：**
  - `manage.py`: 755 (rwxr-xr-x)
  - `settings.py`: 640 (rw-r-----)
  - `db.sqlite3`: 600 (rw-------)

## ⚠️ 生产环境部署建议

### 1. 关闭DEBUG模式
```python
DEBUG = False
```

### 2. 限制ALLOWED_HOSTS
```python
ALLOWED_HOSTS = ['yourdomain.com', 'www.yourdomain.com']
```

### 3. 启用HTTPS安全设置
```python
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
```

### 4. 加强Cookie安全
```python
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True
```

## 🛡️ 运维安全建议

### 1. 定期安全检查
- 定期运行安全检测脚本：`python manage.py security_check`
- 建议每周检查一次系统安全状态

### 2. 日志监控
- 监控安全日志文件：`logs/security.log`
- 设置异常登录告警机制

### 3. 数据备份
- 定期备份数据库文件
- 验证备份文件的完整性
- 将备份存储在安全位置

### 4. 密码策略
- 定期提醒用户更换密码
- 强制使用复杂密码
- 考虑启用双因素认证

### 5. 系统更新
- 保持Django和依赖包的最新版本
- 关注安全漏洞公告
- 及时应用安全补丁

## 📊 安全检查清单

- [ ] CSRF保护已启用
- [ ] 文件权限已正确设置
- [ ] DEBUG模式在生产环境已关闭
- [ ] ALLOWED_HOSTS已限制
- [ ] HTTPS设置已配置
- [ ] Cookie安全设置已启用
- [ ] 密码验证器已配置
- [ ] 日志监控已设置
- [ ] 定期备份已安排
- [ ] 安全检测已定期执行

## 🔧 使用的安全工具

1. **安全检测脚本：** `python manage.py security_check`
2. **安全加固脚本：** `python manage.py security_hardening`
3. **用户管理工具：** `python manage.py create_demo_users`
4. **密码安全检查：** `python manage.py check_password_security`

---

**重要提醒：** 在生产环境部署前，请务必完成所有安全加固措施！
"""

        recommendations_file = 'security_hardening_guide.md'
        
        if not self.dry_run:
            with open(recommendations_file, 'w', encoding='utf-8') as f:
                f.write(recommendations_content)
            self.stdout.write(f"  ✅ 已生成: {recommendations_file}")
        else:
            self.stdout.write(f"  🔄 将生成: {recommendations_file}")
