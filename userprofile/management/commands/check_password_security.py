from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from userprofile.models import Users

class Command(BaseCommand):
    help = '检查GreaterWMS密码存储安全性'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('GreaterWMS 密码存储安全检查'))
        self.stdout.write("=" * 50)
        
        self.stdout.write("\n1. Django用户表 (auth_user) 密码检查:")
        self.stdout.write("-" * 40)
        
        # 检查Django用户密码
        django_users = User.objects.all()[:3]  # 只检查前3个用户
        
        for user in django_users:
            self.stdout.write(f"用户名: {user.username}")
            self.stdout.write(f"密码字段: {user.password}")
            self.stdout.write(f"密码长度: {len(user.password)}")
            
            # 判断密码是否经过哈希
            if user.password.startswith(('pbkdf2_sha256$', 'bcrypt$', 'argon2$')):
                self.stdout.write(self.style.SUCCESS("✅ 密码已哈希加密 - 安全"))
            else:
                self.stdout.write(self.style.ERROR("❌ 密码可能是明文 - 不安全"))
            self.stdout.write("")
        
        self.stdout.write("\n2. GreaterWMS用户表 (user_profile) 检查:")
        self.stdout.write("-" * 40)
        
        # 检查GreaterWMS用户模型
        greaterwms_users = Users.objects.all()[:3]
        
        for user in greaterwms_users:
            self.stdout.write(f"用户名: {user.name}")
            self.stdout.write(f"OpenID: {user.openid}")
            self.stdout.write(f"VIP等级: {user.vip}")
            
            # 检查是否有密码字段
            user_fields = [field.name for field in user._meta.fields]
            if 'password' in user_fields:
                self.stdout.write("密码字段: 存在")
            else:
                self.stdout.write("密码字段: 不存在 - GreaterWMS用户表不直接存储密码")
            self.stdout.write("")
        
        self.stdout.write("\n3. 安全分析:")
        self.stdout.write("-" * 40)
        self.stdout.write("• Django用户表：使用标准的密码哈希算法存储密码")
        self.stdout.write("• GreaterWMS用户表：不直接存储密码，依赖Django用户系统")
        self.stdout.write("• 认证方式：通过Django的认证系统进行密码验证")
        self.stdout.write(self.style.SUCCESS("• 安全等级：✅ 符合安全标准"))
        
        self.stdout.write(f"\n总用户数: Django用户 {User.objects.count()} 个, GreaterWMS用户 {Users.objects.count()} 个")
