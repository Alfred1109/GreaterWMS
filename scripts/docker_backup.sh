#!/bin/bash
# GreaterWMS Docker环境数据库备份脚本
# 用于Docker容器环境的备份自动化

# 配置变量
CONTAINER_NAME="greaterwms_backend"
DOCKER_COMPOSE_FILE="docker-compose.yml"
BACKUP_VOLUME_PATH="./backups"
HOST_BACKUP_PATH="/opt/greaterwms/backups"

# 颜色输出
red() { echo -e "\033[31m$1\033[0m"; }
green() { echo -e "\033[32m$1\033[0m"; }
yellow() { echo -e "\033[33m$1\033[0m"; }
blue() { echo -e "\033[34m$1\033[0m"; }

# 日志函数
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# 检查Docker环境
check_docker_env() {
    log "检查Docker环境..."
    
    # 检查Docker是否运行
    if ! docker info >/dev/null 2>&1; then
        red "错误: Docker服务未运行"
        exit 1
    fi
    
    # 检查容器是否存在并运行
    if ! docker ps | grep -q "$CONTAINER_NAME"; then
        red "错误: 容器 $CONTAINER_NAME 未运行"
        log "尝试启动容器..."
        
        if [ -f "$DOCKER_COMPOSE_FILE" ]; then
            docker-compose up -d "$CONTAINER_NAME"
            sleep 10  # 等待容器启动
            
            if ! docker ps | grep -q "$CONTAINER_NAME"; then
                red "错误: 无法启动容器 $CONTAINER_NAME"
                exit 1
            fi
        else
            red "错误: docker-compose.yml 文件不存在"
            exit 1
        fi
    fi
    
    green "Docker环境检查通过"
}

# 在容器内执行命令
docker_exec() {
    local cmd="$1"
    log "在容器内执行: $cmd"
    docker exec -it "$CONTAINER_NAME" bash -c "cd /GreaterWMS && $cmd"
}

# 执行容器内备份
docker_backup() {
    local backup_type="$1"
    local extra_args="$2"
    
    log "在Docker容器内执行 $backup_type 备份..."
    
    check_docker_env
    
    # 确保备份目录存在
    docker_exec "mkdir -p backups/{full,incremental,hot,logs}"
    
    # 执行备份命令
    local backup_cmd="python manage.py db_backup --type=$backup_type $extra_args"
    
    if docker_exec "$backup_cmd"; then
        green "$backup_type 备份在容器内成功完成"
        
        # 同步备份文件到宿主机（如果配置了卷映射）
        sync_backups_to_host
        
        return 0
    else
        red "$backup_type 备份失败"
        return 1
    fi
}

# 同步备份到宿主机
sync_backups_to_host() {
    if [ -d "$HOST_BACKUP_PATH" ]; then
        log "同步备份文件到宿主机..."
        
        # 创建宿主机备份目录
        mkdir -p "$HOST_BACKUP_PATH"/{full,incremental,hot,logs}
        
        # 从容器复制备份文件
        docker cp "$CONTAINER_NAME:/GreaterWMS/backups/" "$HOST_BACKUP_PATH/../"
        
        if [ $? -eq 0 ]; then
            green "备份文件已同步到宿主机: $HOST_BACKUP_PATH"
        else
            yellow "警告: 备份文件同步到宿主机失败"
        fi
    fi
}

# 列出容器内备份文件
list_docker_backups() {
    log "列出容器内的备份文件..."
    
    check_docker_env
    docker_exec "python manage.py db_restore --list"
}

# 在容器内恢复数据库
docker_restore() {
    local backup_file="$1"
    
    log "在Docker容器内恢复数据库..."
    log "备份文件: $backup_file"
    
    check_docker_env
    
    # 检查备份文件是否存在
    if ! docker_exec "ls backups/*/$backup_file 2>/dev/null"; then
        red "错误: 在容器内未找到备份文件: $backup_file"
        return 1
    fi
    
    # 停止应用服务（如果使用supervisor）
    log "停止应用服务..."
    docker_exec "supervisorctl stop greaterwms" || true
    
    # 执行恢复
    local restore_cmd="python manage.py db_restore --file=backups/*/$backup_file --force"
    
    if docker_exec "$restore_cmd"; then
        green "数据库恢复成功"
        
        # 重启应用服务
        log "重启应用服务..."
        docker_exec "supervisorctl start greaterwms"
        
        return 0
    else
        red "数据库恢复失败"
        
        # 尝试重启服务
        docker_exec "supervisorctl start greaterwms"
        return 1
    fi
}

# 容器内清理过期备份
docker_cleanup() {
    log "在容器内清理过期备份..."
    
    check_docker_env
    docker_exec "python manage.py db_backup --cleanup"
}

# 容器健康检查
docker_health_check() {
    log "执行容器健康检查..."
    
    check_docker_env
    
    # 检查容器状态
    container_status=$(docker inspect --format='{{.State.Status}}' "$CONTAINER_NAME")
    log "容器状态: $container_status"
    
    if [ "$container_status" != "running" ]; then
        red "容器未正常运行"
        return 1
    fi
    
    # 检查数据库连接
    if docker_exec "python manage.py db_restore --verify"; then
        green "数据库连接正常"
    else
        red "数据库连接异常"
        return 1
    fi
    
    # 检查备份目录
    backup_count=$(docker_exec "find backups -name '*.sqlite3*' -type f | wc -l" | tail -1)
    log "备份文件总数: $backup_count"
    
    # 检查容器资源使用情况
    docker stats "$CONTAINER_NAME" --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}"
}

# 创建Docker Compose备份服务
create_backup_service() {
    log "创建Docker Compose备份服务..."
    
    cat > docker-compose.backup.yml << 'EOF'
version: '3.9'

services:
  backup-scheduler:
    image: greaterwms/greaterwms:backend
    container_name: greaterwms_backup_scheduler
    volumes:
      - ./:/GreaterWMS/:rw
      - ./backups:/GreaterWMS/backups:rw
      - /var/log:/var/log:rw
    environment:
      - PYTHONUNBUFFERED=1
      - TZ=Asia/Shanghai
    depends_on:
      - backend
    command: >
      sh -c "
        echo 'Installing cron...' &&
        apt-get update && apt-get install -y cron &&
        echo '# GreaterWMS Database Backup Jobs' > /tmp/crontab &&
        echo '0 2 * * * cd /GreaterWMS && python manage.py db_backup --type=full --compress >> /var/log/backup.log 2>&1' >> /tmp/crontab &&
        echo '0 8,12,16,20 * * 1-5 cd /GreaterWMS && python manage.py db_backup --type=incremental >> /var/log/backup.log 2>&1' >> /tmp/crontab &&
        echo '0 3 * * 0 cd /GreaterWMS && python manage.py db_backup --cleanup >> /var/log/backup.log 2>&1' >> /tmp/crontab &&
        echo '0 * * * * cd /GreaterWMS && python manage.py db_restore --verify >> /var/log/health.log 2>&1' >> /tmp/crontab &&
        crontab /tmp/crontab &&
        echo 'Cron jobs installed. Starting cron daemon...' &&
        service cron start &&
        tail -f /var/log/backup.log /var/log/health.log
      "
    restart: unless-stopped
    networks:
      - basic

networks:
  basic:
    external: true
EOF

    green "Docker Compose备份服务配置文件已创建: docker-compose.backup.yml"
    log "使用以下命令启动备份服务:"
    echo "docker-compose -f docker-compose.backup.yml up -d"
}

# 启动备份服务
start_backup_service() {
    log "启动Docker备份服务..."
    
    if [ -f "docker-compose.backup.yml" ]; then
        docker-compose -f docker-compose.backup.yml up -d
        green "备份服务已启动"
    else
        yellow "备份服务配置文件不存在，正在创建..."
        create_backup_service
        docker-compose -f docker-compose.backup.yml up -d
        green "备份服务已创建并启动"
    fi
}

# 停止备份服务
stop_backup_service() {
    log "停止Docker备份服务..."
    
    if [ -f "docker-compose.backup.yml" ]; then
        docker-compose -f docker-compose.backup.yml down
        green "备份服务已停止"
    else
        yellow "备份服务配置文件不存在"
    fi
}

# 查看备份服务日志
show_backup_logs() {
    log "显示备份服务日志..."
    
    if docker ps | grep -q "greaterwms_backup_scheduler"; then
        docker logs -f greaterwms_backup_scheduler
    else
        red "备份服务未运行"
        return 1
    fi
}

# 显示帮助信息
show_help() {
    cat << EOF
GreaterWMS Docker环境数据库备份脚本

用法: $0 [命令] [参数]

数据库操作命令:
  backup <type> [args]     在容器内执行备份 (type: full|incremental|hot)
  restore <file>           从备份文件恢复数据库
  list                     列出所有可用备份
  cleanup                  清理过期备份文件
  health                   执行健康检查

备份服务命令:
  create-service           创建Docker Compose备份服务
  start-service           启动备份服务
  stop-service            停止备份服务
  logs                    查看备份服务日志

配置变量:
  CONTAINER_NAME          后端容器名称 (当前: $CONTAINER_NAME)
  DOCKER_COMPOSE_FILE     docker-compose文件 (当前: $DOCKER_COMPOSE_FILE)
  HOST_BACKUP_PATH        宿主机备份路径 (当前: $HOST_BACKUP_PATH)

示例:
  $0 backup full --compress              # 执行全量备份并压缩
  $0 backup incremental                  # 执行增量备份
  $0 restore full_backup_20240101_020000.sqlite3  # 恢复指定备份
  $0 list                                # 列出所有备份
  $0 start-service                       # 启动自动备份服务
  $0 logs                                # 查看备份日志

注意事项:
  1. 确保Docker和docker-compose已安装并正常运行
  2. 确保GreaterWMS容器正在运行
  3. 备份服务会在后台持续运行，定时执行备份任务
  4. 生产环境建议配置外部存储卷持久化备份数据
EOF
}

# 主函数
main() {
    case "$1" in
        "backup")
            if [ -z "$2" ]; then
                red "错误: 请指定备份类型 (full|incremental|hot)"
                exit 1
            fi
            docker_backup "$2" "$3"
            ;;
        "restore")
            if [ -z "$2" ]; then
                red "错误: 请指定备份文件名"
                exit 1
            fi
            docker_restore "$2"
            ;;
        "list")
            list_docker_backups
            ;;
        "cleanup")
            docker_cleanup
            ;;
        "health")
            docker_health_check
            ;;
        "create-service")
            create_backup_service
            ;;
        "start-service")
            start_backup_service
            ;;
        "stop-service")
            stop_backup_service
            ;;
        "logs")
            show_backup_logs
            ;;
        "help"|"-h"|"--help"|"")
            show_help
            ;;
        *)
            red "未知命令: $1"
            show_help
            exit 1
            ;;
    esac
}

# 执行主函数
main "$@"
