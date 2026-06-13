#!/usr/bin/env python3
"""微信公众号监控助手 - 命令行工具"""

import os
import sys
import subprocess
import logging
from pathlib import Path

import click
import yaml

logger = logging.getLogger("wechat-article")

# 颜色常量
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def print_banner():
    print(f"""
{CYAN}{BOLD}
 ____    _    _ __  _ __   __ _ _   _ 
|  _ \  | |  | |  _ \| '_ \ / _` | | | |
| | | | | |__| | |_) | | | | (_| | |_| |
|_| |_| |____/|____/|_| |_|\__,_|\__, |
                                 |___/
 微信公众号监控助手 v1.0
{RESET}
""")


def setup_wizard():
    """交互式配置向导"""
    print_banner()
    print(f"{BOLD}欢迎使用微信公众号监控助手配置向导！{RESET}\n")
    print("本向导将引导你完成以下配置：")
    print("  1. 添加关注的公众号")
    print("  2. 配置微信 MP Cookie 和 Token")
    print("  3. 配置 QQ 邮箱 SMTP（可选）")
    print("  4. 设置同步和推送时间\n")

    config = {
        "rsshub": {"base_url": "https://rsshub.app", "timeout": 30},
        "mp": {"cookie": "", "token": ""},
        "subscriptions": [],
        "scheduler": {
            "sync": {"start_hour": 8, "end_hour": 22, "interval_minutes": 60, "run_on_startup": True},
            "digest": {"hour": 22, "minute": 5},
        },
        "output": {"base_dir": "./output", "organize_by_date": True},
        "notifier": {
            "email": {
                "enabled": False,
                "smtp_host": "smtp.qq.com",
                "smtp_port": 465,
                "use_tls": False,
                "sender": "",
                "password": "",
                "recipients": [],
                "digest_mode": True,
            },
            "feishu": {
                "enabled": False,
                "app_id": "",
                "app_secret": "",
                "folder_token": "",
            },
        },
        "database": {"path": "./data/articles.db"},
    }

    # 1. 添加公众号
    print(f"{BOLD}【步骤 1/4】添加关注的公众号{RESET}")
    print("请输入你要监控的公众号 RSS 路径（例如：/wechat/mp/xxxxxxxxxx）")
    print("如果不知道 RSS 路径，可以先运行 tools/query_biz.py 查询 biz\n")

    while True:
        name = input(f"{CYAN}公众号名称（直接回车跳过）: {RESET}").strip()
        if not name:
            break
        rss_path = input(f"{CYAN}RSS 路径: {RESET}").strip()
        config["subscriptions"].append({"name": name, "rss_path": rss_path})
        print(f"  {GREEN}已添加: {name}{RESET}\n")

    # 2. MP Cookie 和 Token
    print(f"\n{BOLD}【步骤 2/4】配置微信 MP Cookie 和 Token{RESET}")
    print("这是获取公众号文章的关键凭证")
    print("获取方法：F12 → Network → 访问公众平台后台 → 复制 Cookie 和 Token\n")
    config["mp"]["cookie"] = input(f"{CYAN}MP Cookie: {RESET}").strip()
    config["mp"]["token"] = input(f"{CYAN}MP Token: {RESET}").strip()

    # 3. 邮箱配置
    print(f"\n{BOLD}【步骤 3/4】配置 QQ 邮箱 SMTP（可选）{RESET}")
    enable_email = input(f"{CYAN}是否启用邮件通知？(y/N): {RESET}").strip().lower()
    if enable_email == "y":
        config["notifier"]["email"]["enabled"] = True
        config["notifier"]["email"]["sender"] = input(f"{CYAN}发件邮箱（QQ邮箱）: {RESET}").strip()
        config["notifier"]["email"]["password"] = input(f"{CYAN}SMTP 授权码: {RESET}").strip()
        recipients = input(f"{CYAN}收件邮箱（多个用逗号分隔，默认同发件邮箱）: {RESET}").strip()
        if recipients:
            config["notifier"]["email"]["recipients"] = [r.strip() for r in recipients.split(",")]
        else:
            config["notifier"]["email"]["recipients"] = [config["notifier"]["email"]["sender"]]
        print(f"  {GREEN}邮箱配置完成{RESET}")
    else:
        print(f"  {YELLOW}跳过邮箱配置，可在 config.yaml 中手动启用{RESET}")

    # 4. 时间设置
    print(f"\n{BOLD}【步骤 4/4】设置同步和推送时间{RESET}")
    start = input(f"{CYAN}同步开始时间（小时，默认 8）: {RESET}").strip()
    end = input(f"{CYAN}同步结束时间（小时，默认 22）: {RESET}").strip()
    hour = input(f"{CYAN}日报推送时间（小时，默认 22）: {RESET}").strip()
    minute = input(f"{CYAN}日报推送分钟（默认 05）: {RESET}").strip()

    if start: config["scheduler"]["sync"]["start_hour"] = int(start)
    if end: config["scheduler"]["sync"]["end_hour"] = int(end)
    if hour: config["scheduler"]["digest"]["hour"] = int(hour)
    if minute: config["scheduler"]["digest"]["minute"] = int(minute)

    # 保存配置
    config_dir = Path(".")
    config_path = config_dir / "config.yaml"
    env_path = config_dir / ".env"

    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)

    # .env 文件（敏感信息）
    env_content = f"""# 微信公众号监控助手 - 环境变量
# 敏感信息，请勿上传到 Git！
MP_COOKIE={config['mp']['cookie']}
MP_TOKEN={config['mp']['token']}
EMAIL_PASSWORD={config['notifier']['email']['password']}
"""
    with open(env_path, "w", encoding="utf-8") as f:
        f.write(env_content)

    print(f"\n{GREEN}{BOLD}配置完成！{RESET}")
    print(f"  - 配置文件: {config_path}")
    print(f"  - 环境变量: {env_path}")
    print(f"\n{BOLD}下一步:{RESET}")
    print(f"  {YELLOW}wechat-monitor run{RESET}    - 立即抓取一次（测试）")
    print(f"  {YELLOW}wechat-monitor daemon{RESET} - 启动守护进程（自动运行）")


@click.group()
def cli():
    """微信公众号监控助手"""
    pass


@cli.command()
def setup():
    """交互式配置向导"""
    setup_wizard()


@cli.command()
def run():
    """运行一次同步任务（立即执行后退出）"""
    print(f"{CYAN}正在运行一次同步任务...{RESET}")

    # 加载环境变量
    from dotenv import load_dotenv
    load_dotenv()

    from app.config import load_config
    from app.logger import setup_logger
    from app.scheduler import create_sync_job

    config = load_config()
    setup_logger()

    sync_job = create_sync_job(config)
    sync_job()

    print(f"\n{GREEN}同步任务完成！{RESET}")


@cli.command()
def daemon():
    """启动守护进程模式（后台持续运行）"""
    print(f"{CYAN}正在启动守护进程...{RESET}")

    # 检查 config.yaml 是否存在
    if not Path("config.yaml").exists():
        print(f"{RED}错误: config.yaml 不存在，请先运行 wechat-monitor setup{RESET}")
        sys.exit(1)

    # 检查 .env 是否存在
    if not Path(".env").exists():
        print(f"{YELLOW}警告: .env 不存在，MP Cookie 和 Token 可能未配置{RESET}")

    # 创建日志目录
    Path("logs").mkdir(parents=True, exist_ok=True)
    log_file = "logs/daemon.log"

    # 跨平台守护进程启动
    if sys.platform == "win32":
        # Windows: 使用 start /B 后台启动
        cmd = f'start /B python main.py > {log_file} 2>&1'
        print(f"  使用 Windows 后台模式启动")
        subprocess.Popen(cmd, shell=True)
    else:
        # Linux/Mac: 使用 nohup
        cmd = f"nohup python main.py > {log_file} 2>&1 &"
        print(f"  使用 nohup 模式启动")
        os.system(cmd)

    # 写入 PID 文件方便后续停止
    pid = os.getpid()
    Path(".daemon.pid").write_text(str(os.getpid()))

    print(f"{GREEN}守护进程已启动！{RESET}")
    print(f"  日志文件: {log_file}")
    print(f"  查看状态: wechat-monitor status")
    print(f"  查看日志: wechat-monitor logs")
    print(f"  停止进程: wechat-monitor stop")


@cli.command()
def status():
    """查看运行状态"""
    print(f"{BOLD}运行状态:{RESET}")

    # 检查主进程
    if sys.platform == "win32":
        result = os.popen('tasklist | findstr "python"').read()
        if "python" in result.lower():
            print(f"  {GREEN}状态: 运行中{RESET}")
        else:
            print(f"  {YELLOW}状态: 未运行{RESET}")
    else:
        result = os.popen('ps aux | grep "main.py" | grep -v grep').read()
        if result:
            print(f"  {GREEN}状态: 运行中{RESET}")
        else:
            print(f"  {YELLOW}状态: 未运行{RESET}")

    # 检查数据库
    db_path = Path("./data/articles.db")
    if db_path.exists():
        from app.repository import ArticleRepository
        repo = ArticleRepository(str(db_path))
        articles = repo.get_unnotified_articles()
        print(f"  数据库: 存在，{len(articles)} 篇未推送文章")
    else:
        print(f"  数据库: 不存在")


@cli.command()
def logs():
    """查看实时日志"""
    log_file = "logs/daemon.log"
    if not Path(log_file).exists():
        print(f"{YELLOW}日志文件不存在，请先启动守护进程{RESET}")
        return

    print(f"{CYAN}实时日志（Ctrl+C 退出）:{RESET}\n")
    os.system(f"tail -f {log_file}")


@cli.command()
def stop():
    """停止守护进程"""
    print(f"{CYAN}正在停止守护进程...{RESET}")

    if sys.platform == "win32":
        os.popen('taskkill /F /IM python.exe')
    else:
        os.popen('pkill -f "python main.py"')

    print(f"{GREEN}守护进程已停止{RESET}")


@cli.command()
def deploy():
    """引导 Docker Compose 云部署"""
    print_banner()
    print(f"{BOLD}Docker Compose 云部署向导{RESET}\n")

    print("本功能将引导你将服务部署到云服务器上")
    print("前提条件：")
    print("  1. 已安装 Docker 和 Docker Compose")
    print("  2. 有云服务器（或本地 Docker 环境）")
    print()

    if not Path("docker-compose.yml").exists():
        print(f"{RED}错误: docker-compose.yml 不存在{RESET}")
        sys.exit(1)

    # 引导用户确认环境变量
    env_path = Path(".env")
    if not env_path.exists():
        print(f"{YELLOW}请先运行 wechat-monitor setup 完成配置{RESET}")
        sys.exit(1)

    print(f"{GREEN}所有文件就绪，执行以下命令部署:{RESET}")
    print(f"\n  {BOLD}docker compose up -d --build{RESET}\n")
    print("部署后可通过以下命令管理：")
    print(f"  {YELLOW}docker compose logs -f{RESET}   - 查看日志")
    print(f"  {YELLOW}docker compose ps{RESET}        - 查看状态")
    print(f"  {YELLOW}docker compose down{RESET}      - 停止服务")


if __name__ == "__main__":
    cli()
