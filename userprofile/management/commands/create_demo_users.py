from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from userprofile.models import Users
import hashlib
from datetime import datetime

class Command(BaseCommand):
    help = '创建GreaterWMS演示用户'

    def generate_openid(self, username):
        """生成openid"""
        return hashlib.md5(f"{username}_{datetime.now()}".encode()).hexdigest()

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('开始创建GreaterWMS演示用户...'))
        
        # 定义要创建的用户列表
        users_to_create = [
            {
                "username": "admin",
                "email": "admin@greaterwms.com",
                "password": "admin123456",
                "name": "系统管理员",
                "vip": 9,
                "is_superuser": True
            },
            {
                "username": "manager",
                "email": "manager@greaterwms.com", 
                "password": "manager123",
                "name": "仓库经理",
                "vip": 7,
                "is_superuser": False
            },
            {
                "username": "operator1",
                "email": "operator1@greaterwms.com",
                "password": "operator123",
                "name": "仓库操作员1",
                "vip": 3,
                "is_superuser": False
            },
            {
                "username": "operator2", 
                "email": "operator2@greaterwms.com",
                "password": "operator123",
                "name": "仓库操作员2",
                "vip": 3,
                "is_superuser": False
            },
            {
                "username": "viewer",
                "email": "viewer@greaterwms.com",
                "password": "viewer123",
                "name": "查看用户",
                "vip": 1,
                "is_superuser": False
            }
        ]
        
        created_count = 0
        
        for user_data in users_to_create:
            self.stdout.write(f"\n正在创建用户: {user_data['username']}")
            
            # 创建或获取Django用户
            django_user, created = User.objects.get_or_create(
                username=user_data['username'],
                defaults={
                    'email': user_data['email'],
                    'is_superuser': user_data['is_superuser'],
                    'is_staff': user_data['is_superuser'],
                    'is_active': True
                }
            )
            
            if created:
                django_user.set_password(user_data['password'])
                django_user.save()
                self.stdout.write(f"  ✅ Django用户已创建: {user_data['username']}")
            else:
                # 更新密码
                django_user.set_password(user_data['password'])
                django_user.save()
                self.stdout.write(f"  ⚠️  Django用户已存在，密码已更新: {user_data['username']}")
            
            # 创建或获取GreaterWMS用户
            openid = self.generate_openid(user_data['username'])
            greaterwms_user, created = Users.objects.get_or_create(
                name=user_data['name'],
                defaults={
                    'vip': user_data['vip'],
                    'openid': openid,
                    'appid': "greaterwms",
                    't_code': f"T{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    'ip': "127.0.0.1",
                    'developer': True if user_data['vip'] >= 5 else False
                }
            )
            
            if created:
                self.stdout.write(f"  ✅ GreaterWMS用户已创建: {user_data['name']}")
                created_count += 1
            else:
                self.stdout.write(f"  ⚠️  GreaterWMS用户已存在: {user_data['name']}")
            
            self.stdout.write(f"     用户名: {user_data['username']}")
            self.stdout.write(f"     密码: {user_data['password']}")
            self.stdout.write(f"     邮箱: {user_data['email']}")
            self.stdout.write(f"     VIP等级: {user_data['vip']}")
        
        self.stdout.write("\n" + "=" * 50)
        self.stdout.write(self.style.SUCCESS(f'🎉 用户创建完成！共处理了 {len(users_to_create)} 个用户'))
        
        self.stdout.write("\n登录信息汇总：")
        self.stdout.write("-" * 30)
        for user_data in users_to_create:
            self.stdout.write(f"{user_data['name']}: {user_data['username']} / {user_data['password']}")
