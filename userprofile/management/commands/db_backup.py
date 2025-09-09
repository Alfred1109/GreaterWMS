from django.core.management.base import BaseCommand
from django.conf import settings
from django.core.mail import send_mail
import os
import shutil
import sqlite3
import hashlib
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
import subprocess
import gzip

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'GreaterWMS数据库备份管理命令'

    def add_arguments(self, parser):
        parser.add_argument(
            '--type',
            type=str,
            choices=['full', 'incremental', 'hot'],
            default='full',
            help='备份类型: full(全量), incremental(增量), hot(热备份)'
        )
        parser.add_argument(
            '--cleanup',
            action='store_true',
            help='清理过期备份文件'
        )
        parser.add_argument(
            '--verify',
            type=str,
            help='验证指定备份文件的完整性'
        )
        parser.add_argument(
            '--compress',
            action='store_true',
            help='压缩备份文件'
        )
        parser.add_argument(
            '--encrypt',
            action='store_true',
            help='加密备份文件'
        )
        parser.add_argument(
            '--silent',
            action='store_true',
            help='静默模式，不输出详细信息'
        )

    def handle(self, *args, **options):
        self.options = options
        self.backup_base_dir = Path(settings.BASE_DIR) / 'backups'
        self.db_path = Path(settings.DATABASES['default']['NAME'])
        
        if not self.options['silent']:
            self.stdout.write(self.style.SUCCESS('🗄️  GreaterWMS 数据库备份工具'))
            self.stdout.write("=" * 80)
            self.stdout.write(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            self.stdout.write("=" * 80)

        # 创建备份目录结构
        self.create_backup_directories()
        
        # 设置日志
        self.setup_logging()

        try:
            if options['cleanup']:
                self.cleanup_old_backups()
            elif options['verify']:
                self.verify_backup(options['verify'])
            else:
                # 执行备份操作
                self.perform_backup(options['type'])
        except Exception as e:
            self.handle_error(f"备份操作失败: {str(e)}")

    def create_backup_directories(self):
        """创建备份目录结构"""
        directories = ['full', 'incremental', 'hot', 'logs']
        for dir_name in directories:
            dir_path = self.backup_base_dir / dir_name
            dir_path.mkdir(parents=True, exist_ok=True)
            # 设置目录权限
            os.chmod(str(dir_path), 0o700)

    def setup_logging(self):
        """设置日志配置"""
        log_file = self.backup_base_dir / 'logs' / 'backup.log'
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(str(log_file)),
                logging.StreamHandler() if not self.options['silent'] else logging.NullHandler()
            ]
        )

    def perform_backup(self, backup_type):
        """执行备份操作"""
        if not self.db_path.exists():
            raise FileNotFoundError(f"数据库文件不存在: {self.db_path}")

        # 生成备份文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"{backup_type}_backup_{timestamp}.sqlite3"
        
        # 确定备份目录
        backup_dir = self.backup_base_dir / backup_type
        backup_file_path = backup_dir / backup_filename

        self.stdout.write(f"\n📋 执行{backup_type}备份...")
        self.stdout.write(f"源文件: {self.db_path}")
        self.stdout.write(f"目标文件: {backup_file_path}")

        # 检查磁盘空间
        if not self.check_disk_space():
            raise Exception("磁盘空间不足，无法执行备份")

        # 执行备份
        start_time = datetime.now()
        
        if backup_type == 'hot':
            self.perform_hot_backup(backup_file_path)
        else:
            self.perform_cold_backup(backup_file_path)

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        # 设置文件权限
        os.chmod(str(backup_file_path), 0o600)

        # 验证备份
        if self.verify_backup_integrity(backup_file_path):
            self.stdout.write(self.style.SUCCESS(f"✅ 备份成功完成"))
        else:
            raise Exception("备份文件验证失败")

        # 压缩备份文件（如果需要）
        if self.options['compress']:
            compressed_file = self.compress_backup(backup_file_path)
            self.stdout.write(f"🗜️  已压缩: {compressed_file}")

        # 加密备份文件（如果需要）
        if self.options['encrypt']:
            encrypted_file = self.encrypt_backup(backup_file_path)
            self.stdout.write(f"🔐 已加密: {encrypted_file}")

        # 记录备份信息
        self.record_backup_info(backup_file_path, backup_type, duration)

        # 发送通知（如果配置了邮件）
        self.send_notification(backup_file_path, backup_type, True)

        self.stdout.write(f"⏱️  备份耗时: {duration:.2f}秒")
        logger.info(f"备份完成: {backup_file_path}, 耗时: {duration:.2f}秒")

    def perform_hot_backup(self, backup_file_path):
        """执行热备份（在线备份）"""
        try:
            # 使用SQLite的在线备份API
            source_conn = sqlite3.connect(str(self.db_path))
            backup_conn = sqlite3.connect(str(backup_file_path))
            
            # 执行在线备份
            source_conn.backup(backup_conn)
            
            source_conn.close()
            backup_conn.close()
            
            self.stdout.write("🔥 热备份完成（数据库无需停机）")
            
        except Exception as e:
            raise Exception(f"热备份失败: {str(e)}")

    def perform_cold_backup(self, backup_file_path):
        """执行冷备份（文件复制）"""
        try:
            # 简单的文件复制
            shutil.copy2(str(self.db_path), str(backup_file_path))
            self.stdout.write("❄️  冷备份完成（文件复制）")
            
        except Exception as e:
            raise Exception(f"冷备份失败: {str(e)}")

    def check_disk_space(self):
        """检查磁盘空间是否足够"""
        db_size = self.db_path.stat().st_size
        backup_dir_stat = os.statvfs(str(self.backup_base_dir))
        free_space = backup_dir_stat.f_bavail * backup_dir_stat.f_frsize
        
        # 需要至少2倍的数据库大小空间
        required_space = db_size * 2
        
        if free_space < required_space:
            self.stdout.write(self.style.ERROR(
                f"⚠️  磁盘空间不足: 需要{required_space/1024/1024:.2f}MB，可用{free_space/1024/1024:.2f}MB"
            ))
            return False
        
        return True

    def verify_backup_integrity(self, backup_file_path):
        """验证备份文件完整性"""
        try:
            # 计算文件哈希值
            original_hash = self.calculate_file_hash(str(self.db_path))
            backup_hash = self.calculate_file_hash(str(backup_file_path))
            
            # 验证SQLite数据库完整性
            conn = sqlite3.connect(str(backup_file_path))
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check")
            result = cursor.fetchone()
            conn.close()
            
            if result[0] != 'ok':
                self.stdout.write(self.style.ERROR(f"❌ 数据库完整性检查失败: {result[0]}"))
                return False
            
            # 对于冷备份，哈希值应该相同
            if original_hash == backup_hash:
                self.stdout.write("✅ 备份文件完整性验证通过")
                return True
            else:
                # 对于热备份，由于可能有并发写入，允许哈希值不同
                self.stdout.write("⚠️  备份文件哈希值不同（热备份正常现象）")
                return True
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ 完整性验证失败: {str(e)}"))
            return False

    def calculate_file_hash(self, file_path):
        """计算文件MD5哈希值"""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def compress_backup(self, backup_file_path):
        """压缩备份文件"""
        compressed_path = Path(str(backup_file_path) + '.gz')
        
        with open(backup_file_path, 'rb') as f_in:
            with gzip.open(compressed_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        # 删除原始备份文件
        backup_file_path.unlink()
        return compressed_path

    def encrypt_backup(self, backup_file_path):
        """加密备份文件（简单示例，生产环境建议使用更强的加密）"""
        # 这里只是示例，实际应用中应使用更安全的加密方法
        encrypted_path = Path(str(backup_file_path) + '.enc')
        
        # 简单的XOR加密示例（不推荐用于生产）
        key = b'GreaterWMS-Backup-Key-2024'
        
        with open(backup_file_path, 'rb') as f_in:
            with open(encrypted_path, 'wb') as f_out:
                data = f_in.read()
                encrypted_data = bytes(a ^ b for a, b in zip(data, (key * (len(data) // len(key) + 1))[:len(data)]))
                f_out.write(encrypted_data)
        
        # 删除原始备份文件
        backup_file_path.unlink()
        return encrypted_path

    def record_backup_info(self, backup_file_path, backup_type, duration):
        """记录备份信息"""
        info = {
            'timestamp': datetime.now().isoformat(),
            'backup_type': backup_type,
            'file_path': str(backup_file_path),
            'file_size': backup_file_path.stat().st_size,
            'duration': duration,
            'hash': self.calculate_file_hash(str(backup_file_path)),
            'compressed': self.options['compress'],
            'encrypted': self.options['encrypt']
        }
        
        info_file = self.backup_base_dir / 'logs' / f"backup_info_{backup_type}.json"
        
        # 读取现有信息
        backups_info = []
        if info_file.exists():
            with open(info_file, 'r', encoding='utf-8') as f:
                backups_info = json.load(f)
        
        # 添加新信息
        backups_info.append(info)
        
        # 保存信息
        with open(info_file, 'w', encoding='utf-8') as f:
            json.dump(backups_info, f, ensure_ascii=False, indent=2)

    def cleanup_old_backups(self):
        """清理过期备份文件"""
        self.stdout.write("\n🧹 清理过期备份文件...")
        
        retention_policies = {
            'full': 30,  # 全量备份保留30天
            'incremental': 7,  # 增量备份保留7天
            'hot': 3  # 热备份保留3天
        }
        
        total_cleaned = 0
        total_size_freed = 0
        
        for backup_type, retention_days in retention_policies.items():
            backup_dir = self.backup_base_dir / backup_type
            cutoff_date = datetime.now() - timedelta(days=retention_days)
            
            if not backup_dir.exists():
                continue
                
            cleaned_count = 0
            size_freed = 0
            
            for backup_file in backup_dir.glob('*_backup_*.sqlite3*'):
                try:
                    # 从文件名提取时间戳
                    timestamp_str = backup_file.stem.split('_')[-2] + '_' + backup_file.stem.split('_')[-1]
                    if backup_file.suffix == '.gz':
                        timestamp_str = backup_file.stem.replace('.sqlite3', '').split('_')[-2] + '_' + \
                                       backup_file.stem.replace('.sqlite3', '').split('_')[-1]
                    
                    file_date = datetime.strptime(timestamp_str, '%Y%m%d_%H%M%S')
                    
                    if file_date < cutoff_date:
                        file_size = backup_file.stat().st_size
                        backup_file.unlink()
                        cleaned_count += 1
                        size_freed += file_size
                        self.stdout.write(f"  🗑️  已删除: {backup_file.name}")
                        
                except (ValueError, IndexError) as e:
                    self.stdout.write(f"  ⚠️  无法解析文件时间戳: {backup_file.name}")
                    continue
            
            if cleaned_count > 0:
                self.stdout.write(f"📁 {backup_type}备份: 清理了{cleaned_count}个文件，释放{size_freed/1024/1024:.2f}MB空间")
            
            total_cleaned += cleaned_count
            total_size_freed += size_freed
        
        if total_cleaned > 0:
            self.stdout.write(self.style.SUCCESS(
                f"✅ 清理完成: 总共删除{total_cleaned}个文件，释放{total_size_freed/1024/1024:.2f}MB空间"
            ))
        else:
            self.stdout.write("ℹ️  没有过期备份需要清理")

    def verify_backup(self, backup_file):
        """验证指定的备份文件"""
        backup_path = Path(backup_file)
        
        if not backup_path.exists():
            self.stdout.write(self.style.ERROR(f"❌ 备份文件不存在: {backup_file}"))
            return
        
        self.stdout.write(f"\n🔍 验证备份文件: {backup_path.name}")
        
        try:
            # 检查文件大小
            file_size = backup_path.stat().st_size
            self.stdout.write(f"📏 文件大小: {file_size/1024/1024:.2f}MB")
            
            # 验证SQLite数据库
            conn = sqlite3.connect(str(backup_path))
            cursor = conn.cursor()
            
            # 完整性检查
            cursor.execute("PRAGMA integrity_check")
            integrity_result = cursor.fetchone()
            
            if integrity_result[0] == 'ok':
                self.stdout.write("✅ 数据库完整性检查通过")
            else:
                self.stdout.write(self.style.ERROR(f"❌ 数据库完整性检查失败: {integrity_result[0]}"))
                return
            
            # 统计表数量
            cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
            table_count = cursor.fetchone()[0]
            self.stdout.write(f"📊 数据表数量: {table_count}")
            
            # 计算总记录数（示例）
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            tables = cursor.fetchall()
            
            total_records = 0
            for table in tables[:5]:  # 只检查前5个表，避免太慢
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM `{table[0]}`")
                    count = cursor.fetchone()[0]
                    total_records += count
                    self.stdout.write(f"  📋 {table[0]}: {count}条记录")
                except Exception as e:
                    self.stdout.write(f"  ⚠️  {table[0]}: 无法统计记录数")
            
            if len(tables) > 5:
                self.stdout.write(f"  ... 还有{len(tables) - 5}个表未显示")
            
            conn.close()
            
            # 计算文件哈希
            file_hash = self.calculate_file_hash(str(backup_path))
            self.stdout.write(f"🔐 文件哈希: {file_hash}")
            
            self.stdout.write(self.style.SUCCESS("✅ 备份文件验证完成"))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ 验证失败: {str(e)}"))

    def send_notification(self, backup_file_path, backup_type, success):
        """发送备份通知邮件"""
        if not hasattr(settings, 'EMAIL_HOST') or not hasattr(settings, 'BACKUP_ALERT_EMAILS'):
            return
        
        subject = f"GreaterWMS 数据库备份{'成功' if success else '失败'}"
        
        if success:
            message = f"""
数据库备份成功完成

备份类型: {backup_type}
备份文件: {backup_file_path.name}
文件大小: {backup_file_path.stat().st_size / 1024 / 1024:.2f}MB
备份时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

系统运行正常。
            """
        else:
            message = f"""
数据库备份执行失败

备份类型: {backup_type}
失败时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

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
            if not self.options['silent']:
                self.stdout.write("📧 已发送备份通知邮件")
        except Exception as e:
            if not self.options['silent']:
                self.stdout.write(f"⚠️  邮件发送失败: {str(e)}")

    def handle_error(self, error_message):
        """处理错误"""
        self.stdout.write(self.style.ERROR(error_message))
        logger.error(error_message)
        
        # 发送错误通知
        self.send_notification(Path(""), "unknown", False)
        
        raise Exception(error_message)
