import logging
from datetime import datetime
from pathlib import Path

from app.config import AppConfig
from app.fetcher import fetch_all_feeds
from app.models import Article
from app.repository import ArticleRepository
from app.scraper import scrape_article
from app.summarizer import TruncateSummarizer

logger = logging.getLogger("wechat-article")

# 记录上次 Cookie 过期提醒时间，避免频繁发邮件
_last_cookie_alert_time = None


def _send_cookie_alert(config: AppConfig):
    """发送 Cookie 过期提醒邮件"""
    global _last_cookie_alert_time

    # 最多每 24 小时提醒一次
    now = datetime.now()
    if _last_cookie_alert_time and (now - _last_cookie_alert_time).total_seconds() < 86400:
        logger.info("Cookie alert already sent within 24h, skipping")
        return

    if not config.notifier.email.enabled or not config.notifier.email.recipients:
        logger.warning("Cookie expired but no email configured for alert")
        return

    try:
        from app.notifier.email import EmailNotifier

        notifier = EmailNotifier(
            smtp_host=config.notifier.email.smtp_host,
            smtp_port=config.notifier.email.smtp_port,
            use_tls=config.notifier.email.use_tls,
            sender=config.notifier.email.sender,
            password=config.notifier.email.password,
            recipients=config.notifier.email.recipients,
        )

        alert_article = Article(
            title="【系统提醒】微信 MP Cookie 已过期",
            article_url="https://mp.weixin.qq.com/",
            author="系统",
            summary="微信公众号 MP API 的 Cookie 已过期，文章同步已停止。请重新登录微信公众平台后台，更新 WA_MP__COOKIE 和 WA_MP__TOKEN 环境变量，然后重启应用。",
        )

        success = notifier.send([alert_article], [alert_article.summary])
        if success:
            _last_cookie_alert_time = now
            logger.info("Cookie expiration alert email sent")
        else:
            logger.error("Failed to send cookie expiration alert email")

    except Exception as e:
        logger.error(f"Error sending cookie alert: {e}")


def create_sync_job(config: AppConfig):
    """创建文章同步 Job：轮询 RSS → 去重 → 抓取 → 转换 → 存储"""

    def sync_job():
        logger.info("Sync job started")
        try:
            repo = ArticleRepository(config.database.path)
            summarizer = TruncateSummarizer(max_length=200)

            # 1. 轮询 RSS / MP API
            articles, cookie_expired = fetch_all_feeds(
                config.subscriptions,
                base_url=config.rsshub.base_url,
                timeout=config.rsshub.timeout,
                mp_cookie=config.mp.cookie,
                mp_token=config.mp.token,
            )

            # 2. Cookie 过期检测
            if cookie_expired:
                logger.error("MP Cookie expired! Sending alert email...")
                _send_cookie_alert(config)
                return  # Cookie 过期，跳过后续抓取

            new_count = 0
            for article in articles:
                # 3. 去重 + Dead-letter 检查
                existing = repo.get_by_url(article.article_url)
                if existing:
                    # Dead-letter: 连续失败超过 5 次，跳过
                    if existing.status == "permanent_failed":
                        logger.debug(f"Article permanently failed, skipping: {article.article_url}")
                        continue

                    # content_hash 变更检测：同一 URL 但内容更新
                    if existing.content_hash and existing.status in ("fetched", "notified"):
                        logger.debug(f"Article already fetched: {article.article_url}")
                        continue

                    # 之前失败的文章，检查 fail_count
                    if existing.fail_count >= 5:
                        logger.warning(f"Article failed {existing.fail_count} times, marking permanent_failed: {article.article_url}")
                        repo.update_status(existing.id, "permanent_failed")
                        continue

                    # 失败次数未达上限，允许重试
                    logger.info(f"Retrying previously failed article (fail_count={existing.fail_count}): {article.article_url}")
                    # 删除旧记录以便重新保存
                    article = existing

                # 4. 抓取
                try:
                    result = scrape_article(
                        article_url=article.article_url,
                        author=article.author,
                        output_base_dir=config.output.base_dir,
                        organize_by_date=config.output.organize_by_date,
                        publish_time=article.publish_time,
                    )
                except Exception as e:
                    logger.error(f"Error scraping {article.article_url}: {e}")
                    if article.id:
                        repo.increment_fail_count(article.id)
                        repo.update_status(article.id, "failed")
                    else:
                        article.status = "failed"
                        article.error_message = str(e)
                        repo.save(article)
                    continue

                if result is None:
                    article.status = "failed"
                    article.error_message = "Scrape returned None"
                    if article.id:
                        repo.increment_fail_count(article.id)
                        repo.update_status(article.id, "failed")
                    else:
                        repo.save(article)
                    continue

                # 5. 生成摘要
                md_content = Path(result["markdown_path"]).read_text(encoding="utf-8")
                summary = summarizer.summarize(md_content)

                # 6. 存储
                article.status = "fetched"
                article.markdown_path = result["markdown_path"]
                article.content_hash = result["content_hash"]
                article.title = result["title"]
                article.summary = summary
                article.fetched_at = datetime.now()
                repo.save(article)
                new_count += 1

            logger.info(f"Sync job completed: {new_count} new articles")

        except Exception as e:
            logger.error(f"Sync job failed: {e}")

    return sync_job


def create_digest_job(config: AppConfig):
    """创建日报推送 Job：查询当日文章 → 发送汇总邮件"""

    def digest_job():
        logger.info("Digest job started")
        try:
            repo = ArticleRepository(config.database.path)
            today = datetime.now().date()

            # 查询当日未通知文章
            articles = repo.get_unnotified_articles(today)
            if not articles:
                logger.info("No new articles today, skipping digest")
                return

            # 发送邮件
            if config.notifier.email.enabled and config.notifier.email.recipients:
                from app.notifier.email import EmailNotifier

                notifier = EmailNotifier(
                    smtp_host=config.notifier.email.smtp_host,
                    smtp_port=config.notifier.email.smtp_port,
                    use_tls=config.notifier.email.use_tls,
                    sender=config.notifier.email.sender,
                    password=config.notifier.email.password,
                    recipients=config.notifier.email.recipients,
                )

                summaries = [a.summary for a in articles]
                success = notifier.send(articles, summaries)

                if success:
                    article_ids = [a.id for a in articles if a.id is not None]
                    if article_ids:
                        repo.batch_update_status(article_ids, "notified")
                    logger.info(f"Digest sent: {len(articles)} articles notified")
                else:
                    logger.error("Failed to send digest email")
            else:
                logger.warning("Email notifier not configured or no recipients")

        except Exception as e:
            logger.error(f"Digest job failed: {e}")

    return digest_job
