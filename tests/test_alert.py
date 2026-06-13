import os
import tempfile
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from app.alert import AlertManager
from app.repository import StateRepository


class TestAlertManager:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test.db")

    def teardown_method(self):
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def test_send_alert_first_time(self):
        """首次告警应发送成功"""
        mock_notifier = MagicMock()
        mock_notifier.send.return_value = True

        manager = AlertManager(self.db_path, mock_notifier)
        result = manager.send_alert(
            key="TEST_ALERT",
            title="测试告警",
            message="这是测试消息",
            level="error",
        )

        assert result is True
        mock_notifier.send.assert_called_once()

        # 验证状态已写入
        state_repo = StateRepository(self.db_path)
        assert state_repo.get("TEST_ALERT") == "测试告警"

    def test_send_alert_cooldown(self):
        """冷却期内不应重复发送"""
        mock_notifier = MagicMock()
        mock_notifier.send.return_value = True

        manager = AlertManager(self.db_path, mock_notifier)

        # 第一次发送
        result1 = manager.send_alert(key="COOLDOWN_TEST", title="告警1", message="消息1")
        assert result1 is True
        assert mock_notifier.send.call_count == 1

        # 第二次发送（在冷却期内）
        result2 = manager.send_alert(key="COOLDOWN_TEST", title="告警2", message="消息2")
        assert result2 is False
        assert mock_notifier.send.call_count == 1  # 没有再次调用

    def test_send_alert_after_cooldown(self):
        """冷却期过后应重新发送"""
        mock_notifier = MagicMock()
        mock_notifier.send.return_value = True

        manager = AlertManager(self.db_path, mock_notifier)

        # 模拟上次告警是 25 小时前
        state_repo = StateRepository(self.db_path)
        state_repo.set("OLD_ALERT", "旧告警")
        # 手动修改 updated_at 为 25 小时前
        conn = state_repo._get_conn()
        old_time = (datetime.now() - timedelta(hours=25)).isoformat()
        conn.execute(
            "UPDATE system_state SET updated_at = ? WHERE key = ?",
            (old_time, "OLD_ALERT"),
        )
        conn.commit()
        conn.close()

        # 再次发送
        result = manager.send_alert(key="OLD_ALERT", title="新告警", message="新消息")
        assert result is True
        mock_notifier.send.assert_called_once()

    def test_send_alert_no_notifier(self):
        """没有 notifier 时不应发送，但也不应崩溃"""
        manager = AlertManager(self.db_path, notifier=None)
        result = manager.send_alert(key="NO_NOTIFIER", title="告警", message="消息")
        assert result is False

    def test_send_cookie_expired_alert(self):
        """Cookie 过期告警格式正确"""
        mock_notifier = MagicMock()
        mock_notifier.send.return_value = True

        manager = AlertManager(self.db_path, mock_notifier)
        result = manager.send_cookie_expired_alert(
            error_code=200003,
            affected_accounts=["测试公众号A", "测试公众号B"],
        )

        assert result is True
        mock_notifier.send.assert_called_once()

        # 验证调用参数
        call_args = mock_notifier.send.call_args
        articles, summaries = call_args[0]
        assert articles[0].title == "MP API Cookie 已失效"
        assert "200003" in summaries[0]
        assert "测试公众号A" in summaries[0]

    def test_send_rsshub_down_alert(self):
        """RSSHub 不可达告警格式正确"""
        mock_notifier = MagicMock()
        mock_notifier.send.return_value = True

        manager = AlertManager(self.db_path, mock_notifier)
        result = manager.send_rsshub_down_alert(rsshub_url="http://localhost:1200")

        assert result is True
        mock_notifier.send.assert_called_once()

        call_args = mock_notifier.send.call_args
        articles, summaries = call_args[0]
        assert articles[0].title == "RSSHub 服务不可达"
        assert "localhost:1200" in summaries[0]
