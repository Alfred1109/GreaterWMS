from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from userprofile.models import Users
from django.utils import timezone

class Command(BaseCommand):
    help = '显示所有用户的详细信息'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('GreaterWMS 用户数据查询'))
        self.stdout.write("=" * 80)
        
        # 查询Django用户
        self.stdout.write("\n📋 Django用户表 (auth_user) - 身份认证数据:")
        self.stdout.write("-" * 80)
        
        django_users = User.objects.all().order_by('id')
        
        # 表头
        self.stdout.write(f"{'ID':<4} {'用户名':<15} {'邮箱':<25} {'超级用户':<8} {'活跃':<6} {'创建时间':<20}")
        self.stdout.write("-" * 80)
        
        for user in django_users:
            created_time = user.date_joined.strftime('%Y-%m-%d %H:%M:%S') if user.date_joined else 'N/A'
            is_super = '是' if user.is_superuser else '否'
            is_active = '是' if user.is_active else '否'
            
            self.stdout.write(
                f"{user.id:<4} {user.username:<15} {user.email:<25} {is_super:<8} {is_active:<6} {created_time:<20}"
            )
        
        # 显示密码哈希样例
        self.stdout.write(f"\n🔒 密码哈希示例 (前3个用户):")
        self.stdout.write("-" * 80)
        for user in django_users[:3]:
            self.stdout.write(f"用户: {user.username}")
            self.stdout.write(f"密码哈希: {user.password}")
            self.stdout.write(f"哈希长度: {len(user.password)} 字符")
            self.stdout.write("")
        
        # 查询GreaterWMS用户
        self.stdout.write("\n📋 GreaterWMS用户表 (user_profile) - 业务权限数据:")
        self.stdout.write("-" * 80)
        
        gwms_users = Users.objects.all().order_by('id')
        
        # 表头
        self.stdout.write(f"{'ID':<4} {'姓名':<15} {'VIP等级':<8} {'开发者':<8} {'OpenID':<35} {'创建时间':<20}")
        self.stdout.write("-" * 80)
        
        for user in gwms_users:
            created_time = user.create_time.strftime('%Y-%m-%d %H:%M:%S') if user.create_time else 'N/A'
            is_dev = '是' if user.developer else '否'
            
            self.stdout.write(
                f"{user.id:<4} {user.name:<15} {user.vip:<8} {is_dev:<8} {user.openid:<35} {created_time:<20}"
            )
        
        # 关联关系分析
        self.stdout.write(f"\n🔗 用户关联关系分析:")
        self.stdout.write("-" * 80)
        
        # 尝试通过用户名关联（这是一个推测性的关联）
        self.stdout.write(f"{'Django用户':<15} {'对应GreaterWMS用户':<20} {'VIP等级':<8} {'匹配状态':<10}")
        self.stdout.write("-" * 80)
        
        for django_user in django_users:
            # 尝试找到可能对应的GreaterWMS用户
            matching_gwms_users = []
            
            # 简单的名称匹配逻辑
            matching_gwms_user = None
            if django_user.username == 'admin':
                matching_gwms_user = gwms_users.filter(name__contains='管理员').first()
            elif django_user.username == 'manager':
                matching_gwms_user = gwms_users.filter(name__contains='经理').first()
            elif django_user.username.startswith('operator'):
                matching_gwms_user = gwms_users.filter(name__contains='操作员').first()
            elif django_user.username == 'viewer':
                matching_gwms_user = gwms_users.filter(name__contains='查看').first()
            
            if matching_gwms_user:
                self.stdout.write(
                    f"{django_user.username:<15} {matching_gwms_user.name:<20} {matching_gwms_user.vip:<8} {'匹配':<10}"
                )
            else:
                self.stdout.write(
                    f"{django_user.username:<15} {'未找到匹配':<20} {'-':<8} {'未匹配':<10}"
                )
        
        # 统计信息
        self.stdout.write(f"\n📊 数据库统计:")
        self.stdout.write("-" * 40)
        self.stdout.write(f"Django用户总数: {django_users.count()}")
        self.stdout.write(f"GreaterWMS用户总数: {gwms_users.count()}")
        self.stdout.write(f"超级用户数量: {django_users.filter(is_superuser=True).count()}")
        self.stdout.write(f"活跃用户数量: {django_users.filter(is_active=True).count()}")
        self.stdout.write(f"VIP用户数量 (等级>5): {gwms_users.filter(vip__gt=5).count()}")
        self.stdout.write(f"开发者用户数量: {gwms_users.filter(developer=True).count()}")
        
        # 登录凭据汇总（仅显示明文密码作为参考）
        self.stdout.write(f"\n🗝️  登录凭据参考 (原始密码):")
        self.stdout.write("-" * 50)
        self.stdout.write("注意: 以下为创建时的明文密码，实际存储为加密哈希值")
        self.stdout.write("-" * 50)
        
        # 这里我们只能显示已知的密码映射
        known_passwords = {
            'admin': 'admin123456',
            'manager': 'manager123', 
            'operator1': 'operator123',
            'operator2': 'operator123',
            'viewer': 'viewer123'
        }
        
        self.stdout.write(f"{'用户名':<15} {'明文密码':<15} {'状态':<10}")
        self.stdout.write("-" * 50)
        
        for django_user in django_users:
            if django_user.username in known_passwords:
                password = known_passwords[django_user.username]
                status = '已知' if django_user.is_active else '禁用'
            else:
                password = '未知'
                status = '旧用户'
            
            self.stdout.write(f"{django_user.username:<15} {password:<15} {status:<10}")
