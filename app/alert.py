import logging
from datetime import datetime, timedelta

from app.repository import StateRepository

logger = logging.getLogger("wechat-article")


class AlertManager:
    """统一告警管理器

    通过 system_state 表实现告警去重（防轰炸），
    同一告警 key 在 cooldown_hours 内只发送一次。
    """

    def __init__(self, db_path: str, notifier=None):
        self.state_repo = StateRepository(db_path)
        self.notifier = notifier  # EmailNotifier 实例，可选

    def send_alert(
        self,
        key: str,
        title: str,
        message: str,
        level: str = "error",
        cooldown_hours: int = 24,
    ) -> bool:
        """发送告警，带去重

        Args:
            key: 告警唯一标识，如 "COOKIE_EXPIRED"
            title: 告警标题
            message: 告警详情
            level: 告警级别 (error / warning / info)
            cooldown_hours: 冷却时间（小时），同一 key 在此时间内不重复发送

        Returns:
            是否实际发送了告警
        """
        # 检查冷却期
        last_alert_time = self.state_repo.get_updated_at(key)
        if last_alert_time:
            elapsed = datetime.now() - last_alert_time
            if elapsed < timedelta(hours=cooldown_hours):
                logger.info(
                    f"Alert '{key}' in cooldown, last sent at {last_alert_time}, "
                    f"skipping (cooldown={cooldown_hours}h)"
                )
                return False

        # 构建邮件内容
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        level_upper = level.upper()

        subject = f"【WeChat Article Monitor】系统告警 - {title}"
        body = f"""<h2>【WeChat Article Monitor】系统告警</h2>
<table style="border-collapse: collapse;">
<tr><td style="padding: 4px 12px;"><strong>告警级别</strong></td><td style="padding: 4px 12px;">{level_upper}</td></tr>
<tr><td style="padding: 4px 12px;"><strong>告警时间</strong></td><td style="padding: 4px 12px;">{now}</td></tr>
<tr><td style="padding: 4px 12px;"><strong>告警标题</strong></td><td style="padding: 4px 12px;">{title}</td></tr>
</table>
<hr>
<div style="white-space: pre-wrap;">{message}</div>"""

        # 发送邮件
        sent = False
        if self.notifier:
            from app.models import Article

            # 用一个 dummy article 作为载体
            dummy = Article(title=title, author="系统", summary=message)
            sent = self.notifier.send([dummy], [message])

        if sent:
            self.state_repo.set(key, title)
            logger.info(f"Alert '{key}' sent successfully")
        else:
            logger.error(f"Failed to send alert '{key}'")

        return sent

    def send_cookie_expired_alert(self, error_code: int, affected_accounts: list[str]) -> bool:
        """Cookie 过期告警的快捷方法"""
        accounts_str = ", ".join(affected_accounts) if affected_accounts else "未知"
        message = f"""MP API Cookie 已失效

错误码：{error_code}
影响范围：{accounts_str}
影响说明：MP API 模式无法获取公众号更新，已自动降级到 RSSHub 模式

处理方式：
1. 用浏览器登录 mp.weixin.qq.com
2. F12 打开开发者工具，获取新的 Cookie 和 Token
3. 更新环境变量 WA_MP__COOKIE 和 WA_MP__TOKEN
4. 重启应用"""

        return self.send_alert(
            key="COOKIE_EXPIRED",
            title="MP API Cookie 已失效",
            message=message,
            level="error",
            cooldown_hours=24,
        )

    def send_rsshub_down_alert(self, rsshub_url: str) -> bool:
        """RSSHub 不可达告警"""
        message = f"""RSSHub 服务不可达

地址：{rsshub_url}
影响：无法通过 RSSHub 获取公众号更新。如果 MP API 也未配置或已失效，则无法获取任何文章。

处理方式：
1. 检查 RSSHub Docker 容器是否运行：docker compose ps
2. 重启容器：docker compose restart rsshub
3. 查看日志：docker compose logs rsshub
4. 如果使用公共实例，可能已被限流，建议自部署 RSSHub"""

        return self.send_alert(
            key="RSSHUB_UNREACHABLE",
            title="RSSHub 服务不可达",
            message=message,
            level="error",
            cooldown_hours=24,
        )
