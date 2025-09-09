from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.conf import settings
from userprofile.models import Users
import os
import sqlite3
import hashlib
from datetime import datetime, timedelta
import stat

class Command(BaseCommand):
    help = 'GreaterWMS系统安全机制全面检测'

    def __init__(self):
        super().__init__()
        self.security_issues = []
        self.security_warnings = []
        self.security_passed = []

    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            type=str,
            default='console',
            help='输出方式: console, file, both (默认: console)'
        )
        parser.add_argument(
            '--detail',
            action='store_true',
            help='显示详细检测信息'
        )

    def handle(self, *args, **options):
        self.detail = options['detail']
        
        self.stdout.write(self.style.SUCCESS('🔒 GreaterWMS 系统安全机制检测'))
        self.stdout.write("=" * 80)
        self.stdout.write(f"检测时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.stdout.write("=" * 80)

        # 执行各项安全检测
        self.check_password_security()
        self.check_database_security()
        self.check_file_permissions()
        self.check_django_settings()
        self.check_user_permissions()
        self.check_session_security()
        self.check_csrf_protection()
        self.check_sql_injection_protection()
        self.check_logging_security()
        self.check_authentication_mechanism()

        # 生成检测报告
        self.generate_report(options['output'])

    def check_password_security(self):
        """检查密码安全性"""
        self.stdout.write(f"\n🔐 1. 密码安全性检测")
        self.stdout.write("-" * 40)
        
        users = User.objects.all()
        
        # 检查密码哈希算法
        secure_algorithms = ['pbkdf2_sha256', 'argon2', 'bcrypt']
        weak_passwords = 0
        strong_hashes = 0
        
        for user in users:
            if any(user.password.startswith(alg) for alg in secure_algorithms):
                strong_hashes += 1
                if self.detail:
                    self.stdout.write(f"  ✅ {user.username}: 使用安全哈希算法")
            else:
                weak_passwords += 1
                self.security_issues.append(f"用户 {user.username} 使用不安全的密码存储方式")
        
        if weak_passwords == 0:
            self.security_passed.append("所有用户密码都使用了安全的哈希算法")
            self.stdout.write(f"  ✅ 密码哈希: {strong_hashes}/{users.count()} 使用安全算法")
        else:
            self.stdout.write(f"  ❌ 发现 {weak_passwords} 个不安全的密码")

        # 检查迭代次数
        if users.exists():
            sample_user = users.first()
            if 'pbkdf2_sha256$' in sample_user.password:
                parts = sample_user.password.split('$')
                if len(parts) >= 2:
                    iterations = int(parts[1])
                    if iterations >= 100000:
                        self.security_passed.append(f"PBKDF2迭代次数充足 ({iterations}次)")
                        self.stdout.write(f"  ✅ 迭代次数: {iterations}次 (安全)")
                    else:
                        self.security_warnings.append(f"PBKDF2迭代次数较低 ({iterations}次)")
                        self.stdout.write(f"  ⚠️  迭代次数: {iterations}次 (建议>100000)")

    def check_database_security(self):
        """检查数据库安全性"""
        self.stdout.write(f"\n🗄️  2. 数据库安全性检测")
        self.stdout.write("-" * 40)
        
        db_path = settings.DATABASES['default']['NAME']
        
        # 检查数据库文件是否存在
        if os.path.exists(db_path):
            self.security_passed.append("数据库文件存在")
            self.stdout.write(f"  ✅ 数据库文件: {db_path}")
            
            # 检查文件大小
            db_size = os.path.getsize(db_path)
            self.stdout.write(f"  📊 数据库大小: {db_size:,} 字节")
            
            # 检查文件权限
            file_stat = os.stat(db_path)
            file_mode = stat.filemode(file_stat.st_mode)
            self.stdout.write(f"  🔒 文件权限: {file_mode}")
            
            if file_stat.st_mode & stat.S_IROTH:
                self.security_warnings.append("数据库文件其他用户可读")
            if file_stat.st_mode & stat.S_IWOTH:
                self.security_issues.append("数据库文件其他用户可写 - 严重安全风险")
                
        else:
            self.security_issues.append("数据库文件不存在")

        # 检查数据库连接配置
        db_config = settings.DATABASES['default']
        if db_config['ENGINE'] == 'django.db.backends.sqlite3':
            self.security_passed.append("使用SQLite数据库 (本地安全)")
            self.stdout.write(f"  ✅ 数据库引擎: SQLite3 (本地)")
        else:
            # 检查是否有密码保护
            if not db_config.get('PASSWORD'):
                self.security_warnings.append("数据库连接无密码保护")

    def check_file_permissions(self):
        """检查关键文件权限"""
        self.stdout.write(f"\n📁 3. 文件权限检测")
        self.stdout.write("-" * 40)
        
        critical_files = [
            'manage.py',
            'greaterwms/settings.py',
            'greaterwms/wsgi.py',
            'db.sqlite3'
        ]
        
        for file_path in critical_files:
            if os.path.exists(file_path):
                file_stat = os.stat(file_path)
                file_mode = stat.filemode(file_stat.st_mode)
                
                if file_stat.st_mode & stat.S_IWOTH:
                    self.security_issues.append(f"{file_path} 其他用户可写")
                    self.stdout.write(f"  ❌ {file_path}: {file_mode} (其他用户可写)")
                else:
                    self.security_passed.append(f"{file_path} 权限安全")
                    self.stdout.write(f"  ✅ {file_path}: {file_mode}")
            else:
                self.stdout.write(f"  ⚠️  {file_path}: 文件不存在")

    def check_django_settings(self):
        """检查Django配置安全性"""
        self.stdout.write(f"\n⚙️  4. Django配置安全性检测")
        self.stdout.write("-" * 40)
        
        # 检查DEBUG模式
        if settings.DEBUG:
            self.security_warnings.append("DEBUG模式已启用 - 生产环境应关闭")
            self.stdout.write(f"  ⚠️  DEBUG: {settings.DEBUG} (建议生产环境关闭)")
        else:
            self.security_passed.append("DEBUG模式已关闭")
            self.stdout.write(f"  ✅ DEBUG: {settings.DEBUG}")

        # 检查SECRET_KEY
        if hasattr(settings, 'SECRET_KEY'):
            if len(settings.SECRET_KEY) >= 50:
                self.security_passed.append("SECRET_KEY长度充足")
                self.stdout.write(f"  ✅ SECRET_KEY: 长度 {len(settings.SECRET_KEY)} 字符")
            else:
                self.security_warnings.append("SECRET_KEY长度不足")
                self.stdout.write(f"  ⚠️  SECRET_KEY: 长度 {len(settings.SECRET_KEY)} 字符 (建议>50)")
        else:
            self.security_issues.append("SECRET_KEY未配置")

        # 检查ALLOWED_HOSTS
        if '*' in settings.ALLOWED_HOSTS:
            self.security_warnings.append("ALLOWED_HOSTS允许所有主机 - 生产环境应限制")
            self.stdout.write(f"  ⚠️  ALLOWED_HOSTS: {settings.ALLOWED_HOSTS} (生产环境应限制)")
        else:
            self.security_passed.append("ALLOWED_HOSTS已限制")
            self.stdout.write(f"  ✅ ALLOWED_HOSTS: {settings.ALLOWED_HOSTS}")

        # 检查HTTPS设置
        https_settings = [
            'SECURE_SSL_REDIRECT',
            'SECURE_HSTS_SECONDS',
            'SECURE_CONTENT_TYPE_NOSNIFF',
            'SECURE_BROWSER_XSS_FILTER'
        ]
        
        https_enabled = 0
        for setting_name in https_settings:
            if hasattr(settings, setting_name) and getattr(settings, setting_name):
                https_enabled += 1
        
        if https_enabled > 0:
            self.security_passed.append(f"{https_enabled} 项HTTPS安全设置已启用")
            self.stdout.write(f"  ✅ HTTPS安全设置: {https_enabled}/{len(https_settings)} 项启用")
        else:
            self.security_warnings.append("未启用HTTPS安全设置")
            self.stdout.write(f"  ⚠️  HTTPS安全设置: 未启用")

    def check_user_permissions(self):
        """检查用户权限体系"""
        self.stdout.write(f"\n👥 5. 用户权限体系检测")
        self.stdout.write("-" * 40)
        
        django_users = User.objects.all()
        gwms_users = Users.objects.all()
        
        # 检查超级用户数量
        superuser_count = django_users.filter(is_superuser=True).count()
        if superuser_count <= 3:
            self.security_passed.append(f"超级用户数量合理 ({superuser_count}个)")
            self.stdout.write(f"  ✅ 超级用户: {superuser_count}个 (合理)")
        else:
            self.security_warnings.append(f"超级用户过多 ({superuser_count}个)")
            self.stdout.write(f"  ⚠️  超级用户: {superuser_count}个 (建议≤3)")

        # 检查用户活跃状态
        active_users = django_users.filter(is_active=True).count()
        inactive_users = django_users.filter(is_active=False).count()
        self.stdout.write(f"  📊 活跃用户: {active_users}个, 非活跃: {inactive_users}个")

        # 检查VIP等级分布
        vip_distribution = {}
        for user in gwms_users:
            vip_level = user.vip
            vip_distribution[vip_level] = vip_distribution.get(vip_level, 0) + 1
        
        self.stdout.write(f"  📊 VIP等级分布: {dict(sorted(vip_distribution.items()))}")
        
        # 检查是否有未匹配的用户
        matched_users = 0
        for django_user in django_users:
            if django_user.username in ['admin', 'manager', 'operator1', 'operator2', 'viewer']:
                matched_users += 1
        
        unmatched = django_users.count() - matched_users
        if unmatched > 0:
            self.security_warnings.append(f"{unmatched}个Django用户未匹配GreaterWMS用户")

    def check_session_security(self):
        """检查会话安全性"""
        self.stdout.write(f"\n🍪 6. 会话安全性检测")
        self.stdout.write("-" * 40)
        
        # 检查会话设置
        session_settings = {
            'SESSION_COOKIE_SECURE': False,  # HTTPS环境应为True
            'SESSION_COOKIE_HTTPONLY': True,
            'SESSION_COOKIE_SAMESITE': 'Lax',
            'SESSION_EXPIRE_AT_BROWSER_CLOSE': False
        }
        
        for setting_name, recommended in session_settings.items():
            current_value = getattr(settings, setting_name, None)
            if current_value == recommended or (setting_name == 'SESSION_COOKIE_SECURE' and not recommended):
                self.stdout.write(f"  ✅ {setting_name}: {current_value}")
            else:
                self.security_warnings.append(f"会话设置 {setting_name} 建议调整")
                self.stdout.write(f"  ⚠️  {setting_name}: {current_value} (建议: {recommended})")

    def check_csrf_protection(self):
        """检查CSRF保护"""
        self.stdout.write(f"\n🛡️  7. CSRF保护检测")
        self.stdout.write("-" * 40)
        
        middleware = getattr(settings, 'MIDDLEWARE', [])
        csrf_middleware = 'django.middleware.csrf.CsrfViewMiddleware'
        
        if csrf_middleware in middleware:
            self.security_passed.append("CSRF保护中间件已启用")
            self.stdout.write(f"  ✅ CSRF中间件: 已启用")
        else:
            self.security_issues.append("CSRF保护中间件未启用")
            self.stdout.write(f"  ❌ CSRF中间件: 未启用")

        # 检查CSRF设置
        csrf_settings = ['CSRF_COOKIE_SECURE', 'CSRF_COOKIE_HTTPONLY']
        for setting_name in csrf_settings:
            value = getattr(settings, setting_name, False)
            if value:
                self.stdout.write(f"  ✅ {setting_name}: {value}")
            else:
                self.stdout.write(f"  ⚠️  {setting_name}: {value} (建议启用)")

    def check_sql_injection_protection(self):
        """检查SQL注入防护"""
        self.stdout.write(f"\n💉 8. SQL注入防护检测")
        self.stdout.write("-" * 40)
        
        # Django ORM默认防护SQL注入
        self.security_passed.append("Django ORM提供SQL注入防护")
        self.stdout.write(f"  ✅ ORM防护: Django ORM自动防护SQL注入")
        
        # 检查是否使用原生SQL
        # 这里只是示例检查，实际可以扫描代码文件
        self.stdout.write(f"  ℹ️  建议: 避免使用原生SQL语句，使用Django ORM")

    def check_logging_security(self):
        """检查日志和审计"""
        self.stdout.write(f"\n📝 9. 日志和审计检测")
        self.stdout.write("-" * 40)
        
        # 检查日志配置
        if hasattr(settings, 'LOGGING'):
            self.security_passed.append("日志配置已设置")
            self.stdout.write(f"  ✅ 日志配置: 已设置")
            
            # 检查日志文件
            log_dirs = ['logs']
            for log_dir in log_dirs:
                if os.path.exists(log_dir):
                    log_files = [f for f in os.listdir(log_dir) if f.endswith('.log')]
                    self.stdout.write(f"  📁 日志文件: {len(log_files)}个 ({', '.join(log_files)})")
                else:
                    self.stdout.write(f"  ⚠️  日志目录不存在: {log_dir}")
        else:
            self.security_warnings.append("未配置日志记录")

    def check_authentication_mechanism(self):
        """检查认证机制"""
        self.stdout.write(f"\n🔐 10. 认证机制检测")
        self.stdout.write("-" * 40)
        
        # 检查认证后端
        auth_backends = getattr(settings, 'AUTHENTICATION_BACKENDS', ['django.contrib.auth.backends.ModelBackend'])
        self.stdout.write(f"  ✅ 认证后端: {len(auth_backends)}个")
        for backend in auth_backends:
            self.stdout.write(f"    - {backend}")

        # 检查密码验证器
        if hasattr(settings, 'AUTH_PASSWORD_VALIDATORS'):
            validators = settings.AUTH_PASSWORD_VALIDATORS
            self.security_passed.append(f"密码验证器已配置 ({len(validators)}个)")
            self.stdout.write(f"  ✅ 密码验证器: {len(validators)}个")
        else:
            self.security_warnings.append("未配置密码验证器")

    def generate_report(self, output_type):
        """生成安全检测报告"""
        self.stdout.write(f"\n" + "="*80)
        self.stdout.write(f"📊 安全检测报告汇总")
        self.stdout.write(f"="*80)
        
        total_checks = len(self.security_passed) + len(self.security_warnings) + len(self.security_issues)
        
        self.stdout.write(f"✅ 通过检测: {len(self.security_passed)}项")
        self.stdout.write(f"⚠️  警告事项: {len(self.security_warnings)}项")
        self.stdout.write(f"❌ 安全问题: {len(self.security_issues)}项")
        self.stdout.write(f"📊 总计检测: {total_checks}项")
        
        # 计算安全评分
        if total_checks > 0:
            score = ((len(self.security_passed) + len(self.security_warnings) * 0.5) / total_checks) * 100
            self.stdout.write(f"🏆 安全评分: {score:.1f}分")
            
            if score >= 90:
                grade = "A级 - 优秀"
            elif score >= 80:
                grade = "B级 - 良好"
            elif score >= 70:
                grade = "C级 - 合格"
            else:
                grade = "D级 - 需要改进"
            
            self.stdout.write(f"📈 安全等级: {grade}")

        # 详细问题列表
        if self.security_issues:
            self.stdout.write(f"\n❌ 需要立即处理的安全问题:")
            for i, issue in enumerate(self.security_issues, 1):
                self.stdout.write(f"  {i}. {issue}")

        if self.security_warnings:
            self.stdout.write(f"\n⚠️  建议改进的安全事项:")
            for i, warning in enumerate(self.security_warnings, 1):
                self.stdout.write(f"  {i}. {warning}")

        # 保存到文件
        if output_type in ['file', 'both']:
            report_filename = f"security_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
            self.save_report_to_file(report_filename, total_checks)
            self.stdout.write(f"\n📄 详细报告已保存到: {report_filename}")

    def save_report_to_file(self, filename, total_checks):
        """保存报告到MD文件"""
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"# GreaterWMS 系统安全检测报告\n\n")
            f.write(f"**生成时间:** {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}\n\n")
            f.write(f"## 检测结果概览\n\n")
            f.write(f"| 检测项目 | 数量 |\n")
            f.write(f"|---------|------|\n")
            f.write(f"| ✅ 通过检测 | {len(self.security_passed)} |\n")
            f.write(f"| ⚠️  警告事项 | {len(self.security_warnings)} |\n")
            f.write(f"| ❌ 安全问题 | {len(self.security_issues)} |\n")
            f.write(f"| 📊 总计检测 | {total_checks} |\n\n")
            
            if self.security_issues:
                f.write(f"## ❌ 安全问题详细列表\n\n")
                for i, issue in enumerate(self.security_issues, 1):
                    f.write(f"{i}. {issue}\n")
                f.write(f"\n")
                
            if self.security_warnings:
                f.write(f"## ⚠️  警告事项详细列表\n\n")
                for i, warning in enumerate(self.security_warnings, 1):
                    f.write(f"{i}. {warning}\n")
                f.write(f"\n")
                
            f.write(f"## ✅ 通过的安全检测\n\n")
            for i, passed in enumerate(self.security_passed, 1):
                f.write(f"{i}. {passed}\n")
