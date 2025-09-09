#!/bin/bash
# GreaterWMS 数据库备份自动化脚本
# 用于Linux环境的定时备份任务

# 配置变量
PROJECT_DIR="/path/to/GreaterWMS"
VENV_DIR="/path/to/venv"
LOG_FILE="/var/log/greaterwms_backup.log"
BACKUP_USER="greaterwms"  # 运行备份的用户
EMAIL_ALERT="admin@company.com"

# 颜色输出函数
red() { echo -e "\033[31m$1\033[0m"; }
green() { echo -e "\033[32m$1\033[0m"; }
yellow() { echo -e "\033[33m$1\033[0m"; }
blue() { echo -e "\033[34m$1\033[0m"; }

# 日志函数
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# 检查函数
check_prerequisites() {
    log "检查运行环境..."
    
    # 检查项目目录
    if [ ! -d "$PROJECT_DIR" ]; then
        red "错误: 项目目录不存在: $PROJECT_DIR"
        exit 1
    fi
    
    # 检查虚拟环境
    if [ ! -f "$VENV_DIR/bin/python" ]; then
        red "错误: Python虚拟环境不存在: $VENV_DIR"
        exit 1
    fi
    
    # 检查数据库文件
    if [ ! -f "$PROJECT_DIR/db.sqlite3" ]; then
        red "错误: 数据库文件不存在: $PROJECT_DIR/db.sqlite3"
        exit 1
    fi
    
    # 检查磁盘空间（至少需要1GB空闲空间）
    AVAILABLE_SPACE=$(df "$PROJECT_DIR" | awk 'NR==2 {print $4}')
    MIN_SPACE=1048576  # 1GB in KB
    
    if [ "$AVAILABLE_SPACE" -lt "$MIN_SPACE" ]; then
        red "警告: 磁盘空间不足 (可用: ${AVAILABLE_SPACE}KB, 需要: ${MIN_SPACE}KB)"
        return 1
    fi
    
    green "环境检查通过"
    return 0
}

# 执行备份
run_backup() {
    local backup_type="$1"
    local extra_args="$2"
    
    log "开始执行 $backup_type 备份..."
    
    cd "$PROJECT_DIR" || {
        red "错误: 无法切换到项目目录: $PROJECT_DIR"
        return 1
    }
    
    # 激活虚拟环境并执行备份
    source "$VENV_DIR/bin/activate"
    
    # 构建备份命令
    backup_cmd="python manage.py db_backup --type=$backup_type $extra_args"
    
    log "执行命令: $backup_cmd"
    
    # 执行备份并捕获输出
    if eval "$backup_cmd"; then
        green "$backup_type 备份成功完成"
        return 0
    else
        red "$backup_type 备份失败"
        return 1
    fi
}

# 发送邮件通知
send_notification() {
    local subject="$1"
    local message="$2"
    
    if command -v mail >/dev/null 2>&1; then
        echo "$message" | mail -s "$subject" "$EMAIL_ALERT"
        log "已发送邮件通知到 $EMAIL_ALERT"
    else
        log "警告: mail命令不可用，无法发送邮件通知"
    fi
}

# 全量备份函数
full_backup() {
    log "=== 开始全量备份 ==="
    
    if ! check_prerequisites; then
        send_notification "GreaterWMS 备份失败" "全量备份失败: 环境检查未通过"
        exit 1
    fi
    
    if run_backup "full" "--compress"; then
        log "=== 全量备份完成 ==="
        send_notification "GreaterWMS 备份成功" "全量备份已成功完成于 $(date)"
    else
        log "=== 全量备份失败 ==="
        send_notification "GreaterWMS 备份失败" "全量备份失败于 $(date)，请检查系统状态"
        exit 1
    fi
}

# 增量备份函数
incremental_backup() {
    log "=== 开始增量备份 ==="
    
    if ! check_prerequisites; then
        log "环境检查未通过，跳过增量备份"
        return 1
    fi
    
    if run_backup "incremental" ""; then
        log "=== 增量备份完成 ==="
    else
        log "=== 增量备份失败 ==="
        # 增量备份失败不发送邮件，避免频繁告警
        return 1
    fi
}

# 热备份函数
hot_backup() {
    log "=== 开始热备份 ==="
    
    if ! check_prerequisites; then
        log "环境检查未通过，跳过热备份"
        return 1
    fi
    
    if run_backup "hot" ""; then
        log "=== 热备份完成 ==="
    else
        log "=== 热备份失败 ==="
        return 1
    fi
}

# 清理过期备份
cleanup_backups() {
    log "=== 开始清理过期备份 ==="
    
    cd "$PROJECT_DIR" || {
        red "错误: 无法切换到项目目录: $PROJECT_DIR"
        return 1
    }
    
    source "$VENV_DIR/bin/activate"
    
    if python manage.py db_backup --cleanup; then
        log "=== 备份清理完成 ==="
        green "过期备份清理成功"
    else
        log "=== 备份清理失败 ==="
        red "过期备份清理失败"
        return 1
    fi
}

# 系统状态检查
health_check() {
    log "=== 系统健康检查 ==="
    
    # 检查数据库连接
    cd "$PROJECT_DIR" || return 1
    source "$VENV_DIR/bin/activate"
    
    if python manage.py db_restore --verify; then
        green "数据库健康检查通过"
    else
        red "数据库健康检查失败"
        send_notification "GreaterWMS 系统告警" "数据库健康检查失败，请立即处理"
        return 1
    fi
    
    # 检查备份目录大小
    BACKUP_SIZE=$(du -sh "$PROJECT_DIR/backups" 2>/dev/null | cut -f1)
    log "当前备份目录大小: $BACKUP_SIZE"
    
    # 检查最近的备份文件
    LATEST_FULL_BACKUP=$(find "$PROJECT_DIR/backups/full" -name "*.sqlite3*" -type f -printf '%T@ %p\n' 2>/dev/null | sort -n | tail -1 | cut -d' ' -f2-)
    
    if [ -n "$LATEST_FULL_BACKUP" ]; then
        BACKUP_AGE=$((($(date +%s) - $(stat -c %Y "$LATEST_FULL_BACKUP")) / 3600))
        log "最新全量备份: $(basename "$LATEST_FULL_BACKUP") (${BACKUP_AGE}小时前)"
        
        # 如果最新备份超过25小时，发送告警
        if [ "$BACKUP_AGE" -gt 25 ]; then
            yellow "警告: 最新全量备份已超过25小时"
            send_notification "GreaterWMS 备份告警" "最新全量备份已超过25小时，请检查备份任务"
        fi
    else
        red "警告: 未找到全量备份文件"
        send_notification "GreaterWMS 备份告警" "未找到全量备份文件，请立即检查"
    fi
}

# 安装crontab任务
install_crontab() {
    log "=== 安装定时任务 ==="
    
    # 备份当前crontab
    crontab -l > /tmp/crontab.backup.$(date +%Y%m%d_%H%M%S) 2>/dev/null || true
    
    # 创建新的crontab条目
    cat > /tmp/greaterwms_crontab << EOF
# GreaterWMS 数据库备份任务
# 每日凌晨2点执行全量备份
0 2 * * * $0 full_backup

# 工作时间每4小时执行增量备份（周一到周五）
0 8,12,16,20 * * 1-5 $0 incremental_backup

# 每周日凌晨3点清理过期备份
0 3 * * 0 $0 cleanup_backups

# 每小时检查系统健康状态
0 * * * * $0 health_check

EOF

    # 合并到现有crontab
    (crontab -l 2>/dev/null || true; cat /tmp/greaterwms_crontab) | crontab -
    
    green "定时任务安装完成"
    log "当前用户的crontab任务:"
    crontab -l | grep -E "(GreaterWMS|$0)" || true
    
    # 清理临时文件
    rm -f /tmp/greaterwms_crontab
}

# 卸载crontab任务
uninstall_crontab() {
    log "=== 卸载定时任务 ==="
    
    # 备份当前crontab
    crontab -l > /tmp/crontab.backup.$(date +%Y%m%d_%H%M%S) 2>/dev/null || true
    
    # 移除GreaterWMS相关的任务
    crontab -l 2>/dev/null | grep -v "$0" | crontab - || true
    
    green "定时任务卸载完成"
}

# 显示帮助信息
show_help() {
    cat << EOF
GreaterWMS 数据库备份自动化脚本

用法: $0 [选项] [命令]

命令:
  full_backup        执行全量备份
  incremental_backup 执行增量备份
  hot_backup         执行热备份
  cleanup_backups    清理过期备份
  health_check       系统健康检查
  install_crontab    安装定时任务
  uninstall_crontab  卸载定时任务
  
选项:
  -h, --help         显示此帮助信息
  -v, --verbose      详细输出模式
  -q, --quiet        静默模式

环境变量:
  PROJECT_DIR        GreaterWMS项目目录 (当前: $PROJECT_DIR)
  VENV_DIR          Python虚拟环境目录 (当前: $VENV_DIR)
  LOG_FILE          日志文件路径 (当前: $LOG_FILE)
  EMAIL_ALERT       邮件告警地址 (当前: $EMAIL_ALERT)

示例:
  $0 full_backup                    # 执行全量备份
  $0 install_crontab                # 安装定时任务
  PROJECT_DIR=/opt/greaterwms $0 health_check  # 指定项目目录并检查健康状态

注意:
  1. 请确保脚本具有可执行权限: chmod +x $0
  2. 建议以专用用户运行: su - $BACKUP_USER -c "$0 full_backup"
  3. 首次使用前请修改脚本顶部的配置变量
  4. 定时任务会自动记录到系统日志
EOF
}

# 主函数
main() {
    case "$1" in
        "full_backup")
            full_backup
            ;;
        "incremental_backup")
            incremental_backup
            ;;
        "hot_backup")
            hot_backup
            ;;
        "cleanup_backups")
            cleanup_backups
            ;;
        "health_check")
            health_check
            ;;
        "install_crontab")
            install_crontab
            ;;
        "uninstall_crontab")
            uninstall_crontab
            ;;
        "-h"|"--help"|"help")
            show_help
            ;;
        "")
            yellow "请指定要执行的命令。使用 --help 查看帮助信息。"
            exit 1
            ;;
        *)
            red "未知命令: $1"
            show_help
            exit 1
            ;;
    esac
}

# 检查参数并执行
if [ "$#" -eq 0 ]; then
    show_help
    exit 1
fi

# 执行主函数
main "$@"
