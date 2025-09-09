# GreaterWMS 数据库备份设置指南

本指南将帮助您快速部署和配置GreaterWMS数据库备份系统。

## 📋 快速开始

### 1. 环境检查

确保您的系统满足以下要求：
- Python 3.8+
- Django 4.1+
- 足够的磁盘空间（建议至少是数据库大小的5倍）
- 系统管理员权限（用于设置定时任务）

### 2. 安装备份系统

```bash
# 1. 确保备份管理命令存在
ls userprofile/management/commands/db_backup.py
ls userprofile/management/commands/db_restore.py

# 2. 创建备份目录
python manage.py db_backup --type=full  # 这将自动创建必要的目录

# 3. 测试备份功能
python manage.py db_backup --type=full --verify=backups/full/latest_backup.sqlite3
```

## 🔧 环境配置

### Linux/macOS 环境

#### 1. 设置自动化脚本

```bash
# 1. 复制自动化脚本
cp scripts/backup_automation.sh /opt/greaterwms/
chmod +x /opt/greaterwms/backup_automation.sh

# 2. 修改配置变量
vi /opt/greaterwms/backup_automation.sh
# 修改以下变量：
# PROJECT_DIR="/opt/greaterwms/GreaterWMS"
# VENV_DIR="/opt/greaterwms/venv"
# LOG_FILE="/var/log/greaterwms_backup.log"
# EMAIL_ALERT="admin@yourcompany.com"

# 3. 测试脚本
/opt/greaterwms/backup_automation.sh full_backup
```

#### 2. 安装定时任务

```bash
# 使用脚本自动安装
/opt/greaterwms/backup_automation.sh install_crontab

# 或手动安装
crontab -e
# 添加以下内容：
# 每日凌晨2点全量备份
0 2 * * * /opt/greaterwms/backup_automation.sh full_backup
# 工作时间每4小时增量备份
0 8,12,16,20 * * 1-5 /opt/greaterwms/backup_automation.sh incremental_backup
# 每周日清理过期备份
0 3 * * 0 /opt/greaterwms/backup_automation.sh cleanup_backups
# 每小时健康检查
0 * * * * /opt/greaterwms/backup_automation.sh health_check
```

### Windows 环境

#### 1. 设置自动化脚本

```batch
# 1. 复制脚本到合适位置
copy scripts\backup_automation.bat C:\GreaterWMS\
# 2. 修改配置变量
notepad C:\GreaterWMS\backup_automation.bat
# 修改以下变量：
# set PROJECT_DIR=C:\GreaterWMS
# set VENV_DIR=C:\GreaterWMS\venv
# set LOG_FILE=C:\logs\greaterwms_backup.log
# set EMAIL_ALERT=admin@yourcompany.com

# 3. 测试脚本
C:\GreaterWMS\backup_automation.bat full_backup
```

#### 2. 创建计划任务

```batch
# 使用脚本自动创建
C:\GreaterWMS\backup_automation.bat create_scheduled_tasks

# 或手动创建
# 全量备份 - 每日凌晨2点
schtasks /create /tn "GreaterWMS Full Backup" /tr "C:\GreaterWMS\backup_automation.bat full_backup" /sc daily /st 02:00

# 增量备份 - 工作日每4小时
schtasks /create /tn "GreaterWMS Inc Backup 08" /tr "C:\GreaterWMS\backup_automation.bat incremental_backup" /sc weekly /d MON,TUE,WED,THU,FRI /st 08:00
schtasks /create /tn "GreaterWMS Inc Backup 12" /tr "C:\GreaterWMS\backup_automation.bat incremental_backup" /sc weekly /d MON,TUE,WED,THU,FRI /st 12:00
schtasks /create /tn "GreaterWMS Inc Backup 16" /tr "C:\GreaterWMS\backup_automation.bat incremental_backup" /sc weekly /d MON,TUE,WED,THU,FRI /st 16:00
schtasks /create /tn "GreaterWMS Inc Backup 20" /tr "C:\GreaterWMS\backup_automation.bat incremental_backup" /sc weekly /d MON,TUE,WED,THU,FRI /st 20:00

# 清理备份 - 每周日凌晨3点
schtasks /create /tn "GreaterWMS Cleanup" /tr "C:\GreaterWMS\backup_automation.bat cleanup_backups" /sc weekly /d SUN /st 03:00

# 健康检查 - 每小时
schtasks /create /tn "GreaterWMS Health Check" /tr "C:\GreaterWMS\backup_automation.bat health_check" /sc hourly
```

### Docker 环境

#### 1. 设置Docker备份

```bash
# 1. 复制Docker备份脚本
cp scripts/docker_backup.sh ./
chmod +x docker_backup.sh

# 2. 修改配置
vi docker_backup.sh
# 修改容器名称等配置

# 3. 测试Docker备份
./docker_backup.sh backup full --compress
./docker_backup.sh list
```

#### 2. 启动自动备份服务

```bash
# 创建并启动备份服务
./docker_backup.sh start-service

# 查看服务状态
docker ps | grep backup

# 查看备份日志
./docker_backup.sh logs
```

## ⚙️ 邮件通知配置

### 1. 在 Django settings.py 中添加邮件配置

```python
# 邮件服务器设置
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'your-email@gmail.com'
EMAIL_HOST_PASSWORD = 'your-app-password'  # 使用应用专用密码

# 备份告警邮件列表
BACKUP_ALERT_EMAILS = [
    'admin@yourcompany.com',
    'dba@yourcompany.com',
    'ops@yourcompany.com'
]
```

### 2. 测试邮件功能

```bash
python manage.py shell
>>> from django.core.mail import send_mail
>>> send_mail('Test', 'This is a test email', 'from@example.com', ['to@example.com'])
```

## 🔒 安全配置

### 1. 文件权限设置

```bash
# 设置备份目录权限
chmod 700 backups/
find backups/ -type f -exec chmod 600 {} \;

# 设置脚本权限
chmod 755 scripts/backup_automation.sh
chmod 644 scripts/backup_automation.bat

# 设置日志文件权限
touch /var/log/greaterwms_backup.log
chmod 640 /var/log/greaterwms_backup.log
```

### 2. 备份加密配置

如需要加密备份，可以安装gpg并配置：

```bash
# 安装gpg
sudo apt-get install gnupg  # Ubuntu/Debian
# 或
sudo yum install gnupg2     # CentOS/RHEL

# 生成密钥对
gpg --gen-key

# 在备份脚本中添加加密选项
python manage.py db_backup --type=full --encrypt
```

## 📊 监控和日志

### 1. 日志配置

```python
# 在 settings.py 中添加备份日志配置
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
        'backup_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/backup.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'db_backup': {
            'handlers': ['backup_file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}
```

### 2. 监控脚本

创建简单的监控脚本：

```bash
#!/bin/bash
# monitor_backup.sh

LOG_FILE="/var/log/greaterwms_backup.log"
ALERT_EMAIL="admin@yourcompany.com"

# 检查最近24小时内是否有成功的全量备份
if ! grep -q "全量备份成功完成" "$LOG_FILE" | grep "$(date -d '24 hours ago' '+%Y-%m-%d')"; then
    echo "警告：24小时内没有成功的全量备份" | mail -s "GreaterWMS 备份告警" "$ALERT_EMAIL"
fi

# 检查备份目录大小
BACKUP_SIZE=$(du -sh backups/ | cut -f1)
echo "当前备份目录大小: $BACKUP_SIZE" >> "$LOG_FILE"
```

## 🔄 恢复测试

### 1. 定期恢复测试

建议每月进行一次恢复测试：

```bash
# 1. 创建测试数据库
python manage.py db_restore --file=backups/full/latest_backup.sqlite3 --test-mode

# 2. 验证测试数据库
python manage.py db_restore --verify --test-mode

# 3. 清理测试文件
rm -f db_test.sqlite3
```

### 2. 自动化恢复测试脚本

```bash
#!/bin/bash
# restore_test.sh

TEST_DB="db_test.sqlite3"
BACKUP_FILE="backups/full/$(ls -t backups/full/*.sqlite3 | head -1 | xargs basename)"

echo "开始恢复测试..."
echo "使用备份文件: $BACKUP_FILE"

# 执行恢复到测试数据库
if python manage.py db_restore --file="$BACKUP_FILE" --test-mode; then
    echo "✅ 恢复测试成功"
    
    # 验证数据库
    if python manage.py db_restore --verify --test-mode; then
        echo "✅ 测试数据库验证通过"
    else
        echo "❌ 测试数据库验证失败"
    fi
    
    # 清理测试文件
    [ -f "$TEST_DB" ] && rm -f "$TEST_DB"
else
    echo "❌ 恢复测试失败"
    exit 1
fi
```

## 🚀 性能优化

### 1. 备份性能调优

```bash
# 对于大型数据库，可以考虑以下优化：

# 1. 使用压缩备份
python manage.py db_backup --type=full --compress

# 2. 在低峰时段执行备份
# 修改crontab时间到凌晨

# 3. 使用SSD存储备份文件
# 将backup目录移到SSD上，使用软链接
```

### 2. 存储优化

```bash
# 1. 定期清理日志
find logs/ -name "*.log" -mtime +30 -delete

# 2. 使用备份文件去重（如果有重复备份）
# fdupes工具可以检测重复文件

# 3. 考虑使用网络存储
# 配置NFS或其他网络存储来存储备份文件
```

## 📞 故障排除

### 常见问题和解决方案

#### 1. 权限问题
```bash
# 问题：Permission denied
# 解决：检查文件和目录权限
ls -la backups/
chmod 700 backups/
```

#### 2. 磁盘空间不足
```bash
# 问题：No space left on device
# 解决：清理过期备份或扩展磁盘空间
python manage.py db_backup --cleanup
df -h
```

#### 3. 邮件发送失败
```bash
# 问题：邮件通知不工作
# 解决：检查邮件配置和网络连接
python manage.py shell
>>> from django.core.mail import send_mail
>>> send_mail('Test', 'Test message', 'from@example.com', ['to@example.com'])
```

#### 4. 定时任务不执行
```bash
# Linux: 检查cron服务
sudo systemctl status cron
sudo systemctl start cron

# 检查crontab配置
crontab -l
```

```batch
REM Windows: 检查任务计划程序
schtasks /query | findstr GreaterWMS

REM 检查任务执行历史
eventvwr.msc
```

## 📚 最佳实践

### 1. 备份策略
- 全量备份：每日执行，保留30天
- 增量备份：工作时间每4小时，保留7天
- 热备份：重要操作前执行，保留3天

### 2. 监控和告警
- 设置备份失败告警
- 定期检查备份文件完整性
- 监控备份目录磁盘使用情况

### 3. 安全措施
- 定期更换备份加密密钥
- 限制备份文件访问权限
- 将备份文件存储到异地

### 4. 恢复准备
- 定期进行恢复演练
- 准备详细的恢复手册
- 建立应急联系机制

---

## 📞 技术支持

如果在设置过程中遇到问题，请联系：

- **技术支持邮箱**: tech-support@greaterwms.com
- **问题反馈**: github.com/Singosgu/GreaterWMS/issues
- **用户文档**: docs.greaterwms.com

---

*最后更新: 2024年1月*  
*维护者: GreaterWMS技术团队*
