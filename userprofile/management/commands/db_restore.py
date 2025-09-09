from django.core.management.base import BaseCommand
from django.conf import settings
from django.core.mail import send_mail
import os
import shutil
import sqlite3
import json
import logging
from datetime import datetime
from pathlib import Path
import subprocess

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'GreaterWMS数据库恢复管理命令'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            help='指定要恢复的备份文件路径'
        )
        parser.add_argument(
            '--list',
            action='store_true',
            help='列出所有可用的备份文件'
        )
        parser.add_argument(
            '--verify',
            action='store_true',
            help='验证恢复后的数据库完整性'
        )
        parser.add_argument(
            '--test-mode',
            action='store_true',
            help='测试模式，恢复到测试数据库（不覆盖生产数据库）'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='强制覆盖现有数据库（跳过确认）'
        )
        parser.add_argument(
            '--backup-current',
            action='store_true',
            default=True,
            help='恢复前备份当前数据库'
        )

    def handle(self, *args, **options):
        self.options = options
        self.backup_base_dir = Path(settings.BASE_DIR) / 'backups'
        self.db_path = Path(settings.DATABASES['default']['NAME'])
        
        self.stdout.write(self.style.SUCCESS('🔄 GreaterWMS 数据库恢复工具'))
        self.stdout.write("=" * 80)
        self.stdout.write(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.stdout.write("=" * 80)

        # 设置日志
        self.setup_logging()

        try:
            if options['list']:
                self.list_available_backups()
            elif options['verify']:
                self.verify_current_database()
            elif options['file']:
                self.restore_from_backup(options['file'])
            else:
                self.stdout.write(self.style.ERROR("❌ 请指定操作参数：--file, --list 或 --verify"))
                self.stdout.write("使用 --help 查看详细帮助信息")
        except Exception as e:
            self.handle_error(f"恢复操作失败: {str(e)}")

    def setup_logging(self):
        """设置日志配置"""
        log_dir = self.backup_base_dir / 'logs'
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / 'restore.log'
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(str(log_file)),
                logging.StreamHandler()
            ]
        )

    def list_available_backups(self):
        """列出所有可用的备份文件"""
        self.stdout.write("\n📋 可用的备份文件:")
        self.stdout.write("-" * 80)
        
        backup_types = ['full', 'incremental', 'hot']
        all_backups = []
        
        for backup_type in backup_types:
            backup_dir = self.backup_base_dir / backup_type
            if not backup_dir.exists():
                continue
            
            # 收集备份文件信息
            for backup_file in sorted(backup_dir.glob('*_backup_*.sqlite3*'), reverse=True):
                try:
                    stat = backup_file.stat()
                    
                    # 解析时间戳
                    filename_parts = backup_file.stem.replace('.sqlite3', '').split('_')
                    if len(filename_parts) >= 4:
                        date_str = filename_parts[-2]
                        time_str = filename_parts[-1]
                        timestamp = datetime.strptime(f"{date_str}_{time_str}", '%Y%m%d_%H%M%S')
                    else:
                        timestamp = datetime.fromtimestamp(stat.st_mtime)
                    
                    backup_info = {
                        'file': backup_file,
                        'type': backup_type,
                        'timestamp': timestamp,
                        'size': stat.st_size,
                        'mtime': stat.st_mtime
                    }
                    all_backups.append(backup_info)
                    
                except Exception as e:
                    self.stdout.write(f"  ⚠️  无法解析备份文件: {backup_file.name} - {str(e)}")
        
        if not all_backups:
            self.stdout.write("❌ 没有找到任何备份文件")
            return
        
        # 按时间排序显示
        all_backups.sort(key=lambda x: x['timestamp'], reverse=True)
        
        self.stdout.write(f"{'类型':<12} {'时间':<20} {'大小':<12} {'文件名'}")
        self.stdout.write("-" * 80)
        
        for backup in all_backups[:20]:  # 只显示最近20个备份
            size_mb = backup['size'] / 1024 / 1024
            timestamp_str = backup['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
            type_display = backup['type'].upper()
            
            self.stdout.write(
                f"{type_display:<12} {timestamp_str:<20} {size_mb:>8.2f}MB {backup['file'].name}"
            )
        
        if len(all_backups) > 20:
            self.stdout.write(f"\n... 还有{len(all_backups) - 20}个备份未显示")
        
        self.stdout.write(f"\n📊 备份统计:")
        for backup_type in backup_types:
            count = len([b for b in all_backups if b['type'] == backup_type])
            if count > 0:
                self.stdout.write(f"  {backup_type.upper()}备份: {count}个")

    def restore_from_backup(self, backup_file_path):
        """从备份文件恢复数据库"""
        backup_path = Path(backup_file_path)
        
        # 检查备份文件是否存在
        if not backup_path.is_absolute():
            # 如果是相对路径，在backups目录下查找
            for backup_type in ['full', 'incremental', 'hot']:
                potential_path = self.backup_base_dir / backup_type / backup_path.name
                if potential_path.exists():
                    backup_path = potential_path
                    break
        
        if not backup_path.exists():
            raise FileNotFoundError(f"备份文件不存在: {backup_file_path}")
        
        self.stdout.write(f"\n🔄 准备恢复数据库...")
        self.stdout.write(f"备份文件: {backup_path}")
        self.stdout.write(f"目标数据库: {self.db_path}")
        
        # 验证备份文件
        if not self.verify_backup_file(backup_path):
            raise Exception("备份文件验证失败，无法恢复")
        
        # 确定目标数据库路径
        if self.options['test_mode']:
            target_db_path = Path(str(self.db_path).replace('.sqlite3', '_test.sqlite3'))
            self.stdout.write(f"🧪 测试模式: 恢复到 {target_db_path}")
        else:
            target_db_path = self.db_path
        
        # 检查是否需要用户确认（生产模式且非强制模式）
        if not self.options['test_mode'] and not self.options['force']:
            if not self.confirm_restore():
                self.stdout.write("❌ 用户取消恢复操作")
                return
        
        # 备份当前数据库
        current_backup_path = None
        if target_db_path.exists() and self.options['backup_current']:
            current_backup_path = self.backup_current_database()
        
        try:
            # 执行恢复
            start_time = datetime.now()
            self.perform_restore(backup_path, target_db_path)
            end_time = datetime.now()
            
            duration = (end_time - start_time).total_seconds()
            
            # 验证恢复后的数据库
            if self.verify_restored_database(target_db_path):
                self.stdout.write(self.style.SUCCESS("✅ 数据库恢复成功"))
                self.stdout.write(f"⏱️  恢复耗时: {duration:.2f}秒")
                
                # 记录恢复操作
                self.record_restore_info(backup_path, target_db_path, duration, True)
                
                # 发送通知
                self.send_notification(backup_path, target_db_path, True)
                
                logger.info(f"数据库恢复成功: {backup_path} -> {target_db_path}")
                
            else:
                raise Exception("恢复后数据库验证失败")
                
        except Exception as e:
            # 恢复失败，尝试回滚
            if current_backup_path and not self.options['test_mode']:
                self.stdout.write("⚠️  恢复失败，尝试回滚到原始数据库...")
                try:
                    shutil.copy2(str(current_backup_path), str(target_db_path))
                    self.stdout.write("✅ 已回滚到原始数据库")
                except Exception as rollback_error:
                    self.stdout.write(self.style.ERROR(f"❌ 回滚失败: {str(rollback_error)}"))
            
            # 记录恢复失败
            self.record_restore_info(backup_path, target_db_path, 0, False, str(e))
            self.send_notification(backup_path, target_db_path, False, str(e))
            
            raise e

    def verify_backup_file(self, backup_path):
        """验证备份文件的完整性"""
        self.stdout.write(f"🔍 验证备份文件...")
        
        try:
            # 检查文件大小
            file_size = backup_path.stat().st_size
            if file_size == 0:
                self.stdout.write(self.style.ERROR("❌ 备份文件为空"))
                return False
            
            self.stdout.write(f"📏 文件大小: {file_size/1024/1024:.2f}MB")
            
            # 验证SQLite数据库格式
            conn = sqlite3.connect(str(backup_path))
            cursor = conn.cursor()
            
            # 完整性检查
            cursor.execute("PRAGMA integrity_check")
            result = cursor.fetchone()
            
            if result[0] != 'ok':
                self.stdout.write(self.style.ERROR(f"❌ 数据库完整性检查失败: {result[0]}"))
                conn.close()
                return False
            
            # 检查是否有数据表
            cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
            table_count = cursor.fetchone()[0]
            
            if table_count == 0:
                self.stdout.write(self.style.ERROR("❌ 备份文件中没有数据表"))
                conn.close()
                return False
            
            conn.close()
            self.stdout.write("✅ 备份文件验证通过")
            return True
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ 备份文件验证失败: {str(e)}"))
            return False

    def confirm_restore(self):
        """确认恢复操作"""
        self.stdout.write("\n⚠️  警告: 这将覆盖当前的数据库！")
        self.stdout.write("当前数据库将被备份到临时位置。")
        
        while True:
            response = input("\n是否确认继续恢复操作？(yes/no): ").lower().strip()
            if response in ['yes', 'y']:
                return True
            elif response in ['no', 'n']:
                return False
            else:
                self.stdout.write("请输入 'yes' 或 'no'")

    def backup_current_database(self):
        """备份当前数据库"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"pre_restore_backup_{timestamp}.sqlite3"
        backup_path = self.backup_base_dir / 'hot' / backup_filename
        
        # 确保备份目录存在
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.stdout.write(f"📦 备份当前数据库到: {backup_path.name}")
        
        try:
            shutil.copy2(str(self.db_path), str(backup_path))
            os.chmod(str(backup_path), 0o600)
            self.stdout.write("✅ 当前数据库备份完成")
            return backup_path
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ 当前数据库备份失败: {str(e)}"))
            raise e

    def perform_restore(self, backup_path, target_db_path):
        """执行数据库恢复"""
        self.stdout.write("🔄 正在恢复数据库...")
        
        try:
            # 如果目标数据库存在，先删除
            if target_db_path.exists():
                target_db_path.unlink()
            
            # 复制备份文件到目标位置
            shutil.copy2(str(backup_path), str(target_db_path))
            
            # 设置正确的文件权限
            os.chmod(str(target_db_path), 0o600)
            
            self.stdout.write("✅ 文件复制完成")
            
        except Exception as e:
            raise Exception(f"数据库恢复失败: {str(e)}")

    def verify_restored_database(self, db_path):
        """验证恢复后的数据库"""
        self.stdout.write("🔍 验证恢复后的数据库...")
        
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            # 完整性检查
            cursor.execute("PRAGMA integrity_check")
            result = cursor.fetchone()
            
            if result[0] != 'ok':
                self.stdout.write(self.style.ERROR(f"❌ 数据库完整性检查失败: {result[0]}"))
                conn.close()
                return False
            
            # 检查关键表是否存在（根据你的应用调整）
            key_tables = ['django_migrations', 'auth_user', 'goods_goods']  # 示例表名
            for table in key_tables:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    self.stdout.write(f"  📋 {table}: {count}条记录")
                except sqlite3.OperationalError:
                    # 表可能不存在，这是正常的
                    continue
            
            conn.close()
            self.stdout.write("✅ 恢复后数据库验证通过")
            return True
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ 数据库验证失败: {str(e)}"))
            return False

    def verify_current_database(self):
        """验证当前数据库的完整性"""
        if not self.db_path.exists():
            self.stdout.write(self.style.ERROR(f"❌ 当前数据库文件不存在: {self.db_path}"))
            return
        
        self.stdout.write(f"\n🔍 验证当前数据库: {self.db_path}")
        
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            # 文件大小
            file_size = self.db_path.stat().st_size
            self.stdout.write(f"📏 文件大小: {file_size/1024/1024:.2f}MB")
            
            # 完整性检查
            cursor.execute("PRAGMA integrity_check")
            result = cursor.fetchone()
            
            if result[0] == 'ok':
                self.stdout.write("✅ 数据库完整性检查通过")
            else:
                self.stdout.write(self.style.ERROR(f"❌ 数据库完整性检查失败: {result[0]}"))
                return
            
            # 表统计
            cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
            table_count = cursor.fetchone()[0]
            self.stdout.write(f"📊 数据表数量: {table_count}")
            
            # 显示一些表的记录数
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
            tables = cursor.fetchall()
            
            self.stdout.write("\n📋 主要数据表记录数:")
            for i, table in enumerate(tables):
                if i >= 10:  # 只显示前10个表
                    self.stdout.write(f"  ... 还有{len(tables) - 10}个表未显示")
                    break
                
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM `{table[0]}`")
                    count = cursor.fetchone()[0]
                    self.stdout.write(f"  📋 {table[0]}: {count:,}条记录")
                except Exception as e:
                    self.stdout.write(f"  ⚠️  {table[0]}: 无法统计")
            
            conn.close()
            self.stdout.write(self.style.SUCCESS("\n✅ 当前数据库验证完成"))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ 数据库验证失败: {str(e)}"))

    def record_restore_info(self, backup_path, target_db_path, duration, success, error_msg=None):
        """记录恢复操作信息"""
        info = {
            'timestamp': datetime.now().isoformat(),
            'backup_file': str(backup_path),
            'target_database': str(target_db_path),
            'duration': duration,
            'success': success,
            'test_mode': self.options['test_mode'],
            'error_message': error_msg
        }
        
        log_dir = self.backup_base_dir / 'logs'
        log_dir.mkdir(parents=True, exist_ok=True)
        info_file = log_dir / 'restore_history.json'
        
        # 读取现有历史
        restore_history = []
        if info_file.exists():
            try:
                with open(info_file, 'r', encoding='utf-8') as f:
                    restore_history = json.load(f)
            except Exception:
                restore_history = []
        
        # 添加新记录
        restore_history.append(info)
        
        # 只保留最近100条记录
        if len(restore_history) > 100:
            restore_history = restore_history[-100:]
        
        # 保存历史
        with open(info_file, 'w', encoding='utf-8') as f:
            json.dump(restore_history, f, ensure_ascii=False, indent=2)

    def send_notification(self, backup_path, target_db_path, success, error_msg=None):
        """发送恢复通知邮件"""
        if not hasattr(settings, 'EMAIL_HOST') or not hasattr(settings, 'BACKUP_ALERT_EMAILS'):
            return
        
        subject = f"GreaterWMS 数据库恢复{'成功' if success else '失败'}"
        
        if success:
            message = f"""
数据库恢复成功完成

备份文件: {backup_path.name}
目标数据库: {target_db_path.name}
恢复时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
测试模式: {'是' if self.options['test_mode'] else '否'}

数据库已成功恢复并验证完成。
            """
        else:
            message = f"""
数据库恢复执行失败

备份文件: {backup_path.name}
目标数据库: {target_db_path.name}
失败时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
错误信息: {error_msg}

请检查系统状态并及时处理。
            """
        
        try:
            send_mail(
                subject,
                message,
                settings.EMAIL_HOST_USER,
                settings.BACKUP_ALERT_EMAILS,
                fail_silently=False,
            )
            self.stdout.write("📧 已发送恢复通知邮件")
        except Exception as e:
            self.stdout.write(f"⚠️  邮件发送失败: {str(e)}")

    def handle_error(self, error_message):
        """处理错误"""
        self.stdout.write(self.style.ERROR(error_message))
        logger.error(error_message)
        raise Exception(error_message)
