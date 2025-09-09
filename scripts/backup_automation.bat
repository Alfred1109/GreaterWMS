@echo off
:: GreaterWMS 数据库备份自动化脚本 (Windows版本)
:: 用于Windows环境的定时备份任务

:: 配置变量 - 请根据实际情况修改
set PROJECT_DIR=C:\path\to\GreaterWMS
set VENV_DIR=C:\path\to\venv
set LOG_FILE=C:\logs\greaterwms_backup.log
set EMAIL_ALERT=admin@company.com

:: 设置编码为UTF-8
chcp 65001 >nul

:: 创建日志目录
if not exist "C:\logs" mkdir "C:\logs"

:: 日志函数
goto :main

:log_message
echo [%date% %time%] %~1 >> "%LOG_FILE%"
echo [%date% %time%] %~1
goto :eof

:check_prerequisites
call :log_message "检查运行环境..."

:: 检查项目目录
if not exist "%PROJECT_DIR%" (
    call :log_message "错误: 项目目录不存在: %PROJECT_DIR%"
    exit /b 1
)

:: 检查虚拟环境
if not exist "%VENV_DIR%\Scripts\python.exe" (
    call :log_message "错误: Python虚拟环境不存在: %VENV_DIR%"
    exit /b 1
)

:: 检查数据库文件
if not exist "%PROJECT_DIR%\db.sqlite3" (
    call :log_message "错误: 数据库文件不存在: %PROJECT_DIR%\db.sqlite3"
    exit /b 1
)

call :log_message "环境检查通过"
goto :eof

:run_backup
set backup_type=%~1
set extra_args=%~2

call :log_message "开始执行 %backup_type% 备份..."

:: 切换到项目目录
cd /d "%PROJECT_DIR%" || (
    call :log_message "错误: 无法切换到项目目录: %PROJECT_DIR%"
    exit /b 1
)

:: 激活虚拟环境
call "%VENV_DIR%\Scripts\activate.bat"

:: 执行备份命令
set backup_cmd=%VENV_DIR%\Scripts\python.exe manage.py db_backup --type=%backup_type% %extra_args%

call :log_message "执行命令: %backup_cmd%"

%backup_cmd%
if %ERRORLEVEL% equ 0 (
    call :log_message "%backup_type% 备份成功完成"
    exit /b 0
) else (
    call :log_message "%backup_type% 备份失败"
    exit /b 1
)

:send_notification
set subject=%~1
set message=%~2

:: Windows可以使用blat或其他邮件工具发送邮件
:: 这里提供一个简单的示例，实际使用时请配置邮件工具
call :log_message "邮件通知: %subject% - %message%"

:: 如果安装了blat工具，可以使用以下命令发送邮件
:: echo %message% | blat - -to %EMAIL_ALERT% -subject "%subject%"

goto :eof

:full_backup
call :log_message "=== 开始全量备份 ==="

call :check_prerequisites
if %ERRORLEVEL% neq 0 (
    call :send_notification "GreaterWMS 备份失败" "全量备份失败: 环境检查未通过"
    exit /b 1
)

call :run_backup "full" "--compress"
if %ERRORLEVEL% equ 0 (
    call :log_message "=== 全量备份完成 ==="
    call :send_notification "GreaterWMS 备份成功" "全量备份已成功完成于 %date% %time%"
) else (
    call :log_message "=== 全量备份失败 ==="
    call :send_notification "GreaterWMS 备份失败" "全量备份失败于 %date% %time%，请检查系统状态"
    exit /b 1
)
goto :eof

:incremental_backup
call :log_message "=== 开始增量备份 ==="

call :check_prerequisites
if %ERRORLEVEL% neq 0 (
    call :log_message "环境检查未通过，跳过增量备份"
    exit /b 1
)

call :run_backup "incremental" ""
if %ERRORLEVEL% equ 0 (
    call :log_message "=== 增量备份完成 ==="
) else (
    call :log_message "=== 增量备份失败 ==="
    exit /b 1
)
goto :eof

:hot_backup
call :log_message "=== 开始热备份 ==="

call :check_prerequisites
if %ERRORLEVEL% neq 0 (
    call :log_message "环境检查未通过，跳过热备份"
    exit /b 1
)

call :run_backup "hot" ""
if %ERRORLEVEL% equ 0 (
    call :log_message "=== 热备份完成 ==="
) else (
    call :log_message "=== 热备份失败 ==="
    exit /b 1
)
goto :eof

:cleanup_backups
call :log_message "=== 开始清理过期备份 ==="

cd /d "%PROJECT_DIR%" || (
    call :log_message "错误: 无法切换到项目目录: %PROJECT_DIR%"
    exit /b 1
)

call "%VENV_DIR%\Scripts\activate.bat"

%VENV_DIR%\Scripts\python.exe manage.py db_backup --cleanup
if %ERRORLEVEL% equ 0 (
    call :log_message "=== 备份清理完成 ==="
) else (
    call :log_message "=== 备份清理失败 ==="
    exit /b 1
)
goto :eof

:health_check
call :log_message "=== 系统健康检查 ==="

cd /d "%PROJECT_DIR%" || exit /b 1
call "%VENV_DIR%\Scripts\activate.bat"

%VENV_DIR%\Scripts\python.exe manage.py db_restore --verify
if %ERRORLEVEL% equ 0 (
    call :log_message "数据库健康检查通过"
) else (
    call :log_message "数据库健康检查失败"
    call :send_notification "GreaterWMS 系统告警" "数据库健康检查失败，请立即处理"
    exit /b 1
)

:: 检查备份目录大小
for /f "tokens=3" %%a in ('dir "%PROJECT_DIR%\backups" /-c ^| findstr /E "bytes"') do (
    call :log_message "当前备份目录大小: %%a 字节"
)

:: 检查最近的备份文件
for /f "delims=" %%i in ('dir "%PROJECT_DIR%\backups\full\*.sqlite3*" /b /o-d 2^>nul ^| head -1') do (
    set LATEST_BACKUP=%%i
    call :log_message "最新全量备份: %%i"
)

goto :eof

:create_scheduled_tasks
call :log_message "=== 创建Windows计划任务 ==="

:: 创建全量备份任务 - 每日凌晨2点
schtasks /create /tn "GreaterWMS Full Backup" /tr "%~f0 full_backup" /sc daily /st 02:00 /f
if %ERRORLEVEL% equ 0 (
    call :log_message "全量备份计划任务创建成功"
) else (
    call :log_message "全量备份计划任务创建失败"
)

:: 创建增量备份任务 - 工作日每4小时
schtasks /create /tn "GreaterWMS Incremental Backup 1" /tr "%~f0 incremental_backup" /sc weekly /d MON,TUE,WED,THU,FRI /st 08:00 /f
schtasks /create /tn "GreaterWMS Incremental Backup 2" /tr "%~f0 incremental_backup" /sc weekly /d MON,TUE,WED,THU,FRI /st 12:00 /f
schtasks /create /tn "GreaterWMS Incremental Backup 3" /tr "%~f0 incremental_backup" /sc weekly /d MON,TUE,WED,THU,FRI /st 16:00 /f
schtasks /create /tn "GreaterWMS Incremental Backup 4" /tr "%~f0 incremental_backup" /sc weekly /d MON,TUE,WED,THU,FRI /st 20:00 /f

:: 创建清理任务 - 每周日凌晨3点
schtasks /create /tn "GreaterWMS Cleanup Backups" /tr "%~f0 cleanup_backups" /sc weekly /d SUN /st 03:00 /f

:: 创建健康检查任务 - 每小时
schtasks /create /tn "GreaterWMS Health Check" /tr "%~f0 health_check" /sc hourly /f

call :log_message "Windows计划任务创建完成"
call :log_message "您可以使用 'schtasks /query | findstr GreaterWMS' 查看创建的任务"

goto :eof

:delete_scheduled_tasks
call :log_message "=== 删除Windows计划任务 ==="

schtasks /delete /tn "GreaterWMS Full Backup" /f >nul 2>&1
schtasks /delete /tn "GreaterWMS Incremental Backup 1" /f >nul 2>&1
schtasks /delete /tn "GreaterWMS Incremental Backup 2" /f >nul 2>&1
schtasks /delete /tn "GreaterWMS Incremental Backup 3" /f >nul 2>&1
schtasks /delete /tn "GreaterWMS Incremental Backup 4" /f >nul 2>&1
schtasks /delete /tn "GreaterWMS Cleanup Backups" /f >nul 2>&1
schtasks /delete /tn "GreaterWMS Health Check" /f >nul 2>&1

call :log_message "Windows计划任务删除完成"
goto :eof

:show_help
echo GreaterWMS 数据库备份自动化脚本 (Windows版本)
echo.
echo 用法: %~nx0 [命令]
echo.
echo 命令:
echo   full_backup              执行全量备份
echo   incremental_backup       执行增量备份
echo   hot_backup               执行热备份
echo   cleanup_backups          清理过期备份
echo   health_check             系统健康检查
echo   create_scheduled_tasks   创建Windows计划任务
echo   delete_scheduled_tasks   删除Windows计划任务
echo.
echo 配置变量 (请在脚本开头修改):
echo   PROJECT_DIR     GreaterWMS项目目录 (当前: %PROJECT_DIR%)
echo   VENV_DIR        Python虚拟环境目录 (当前: %VENV_DIR%)
echo   LOG_FILE        日志文件路径 (当前: %LOG_FILE%)
echo   EMAIL_ALERT     邮件告警地址 (当前: %EMAIL_ALERT%)
echo.
echo 示例:
echo   %~nx0 full_backup                        # 执行全量备份
echo   %~nx0 create_scheduled_tasks             # 创建计划任务
echo.
echo 注意:
echo   1. 首次使用前请修改脚本顶部的配置变量
echo   2. 创建计划任务需要管理员权限
echo   3. 建议在专用的服务账户下运行
echo   4. 可以使用Windows事件查看器查看任务执行日志
goto :eof

:main
if "%~1"=="" goto show_help
if "%~1"=="help" goto show_help
if "%~1"=="/?" goto show_help
if "%~1"=="--help" goto show_help

if "%~1"=="full_backup" goto full_backup
if "%~1"=="incremental_backup" goto incremental_backup
if "%~1"=="hot_backup" goto hot_backup
if "%~1"=="cleanup_backups" goto cleanup_backups
if "%~1"=="health_check" goto health_check
if "%~1"=="create_scheduled_tasks" goto create_scheduled_tasks
if "%~1"=="delete_scheduled_tasks" goto delete_scheduled_tasks

echo 未知命令: %~1
echo 使用 "%~nx0 help" 查看帮助信息
exit /b 1
