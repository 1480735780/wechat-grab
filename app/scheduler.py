import logging
from datetime import datetime
from pathlib import Path

from app.alert import AlertManager
from app.config import AppConfig
from app.fetcher import fetch_all_feeds
from app.models import Article
from app.repository import ArticleRepository
from app.scraper import scrape_article
from app.summarizer import TruncateSummarizer

logger = logging.getLogger("wechat-article")


def _create_notifier(config: AppConfig):
    """创建 EmailNotifier 实例"""
    if not config.notifier.email.enabled or not config.notifier.email.recipients:
        return None
    from app.notifier.email import EmailNotifier
    return EmailNotifier(
        smtp_host=config.notifier.email.smtp_host,
        smtp_port=config.notifier.email.smtp_port,
        use_tls=config.notifier.email.use_tls,
        sender=config.notifier.email.sender,
        password=config.notifier.email.password,
        recipients=config.notifier.email.recipients,
    )


def create_sync_job(config: AppConfig):
    """创建文章同步 Job：轮询 RSS → 去重 → 抓取 → 转换 → 存储"""

    def sync_job():
        logger.info("Sync job started")
        try:
            repo = ArticleRepository(config.database.path)
            summarizer = TruncateSummarizer(max_length=200)
            notifier = _create_notifier(config)
            alert_manager = AlertManager(config.database.path, notifier)

            # 1. 轮询 MP API / RSS
            fetch_result = fetch_all_feeds(
                config.subscriptions,
                base_url=config.rsshub.base_url,
                timeout=config.rsshub.timeout,
                mp_cookie=config.mp.cookie,
                mp_token=config.mp.token,
            )

            # 2. 处理告警
            for alert in fetch_result.alerts:
                if alert.key == "COOKIE_EXPIRED":
                    affected = [s.name for s in config.subscriptions]
                    alert_manager.send_cookie_expired_alert(alert.error_code, affected)
                elif alert.key == "RSSHUB_UNREACHABLE":
                    alert_manager.send_rsshub_down_alert(config.rsshub.base_url)
                else:
                    alert_manager.send_alert(
                        key=alert.key,
                        title=alert.title,
                        message=alert.message,
                        level=alert.level,
                    )

            # 3. 处理文章
            new_count = 0
            for article in fetch_result.articles:
                # 去重
                if repo.exists_by_url(article.article_url):
                    logger.debug(f"Article already exists: {article.article_url}")
                    continue

                # 抓取
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
                    article.status = "failed"
                    article.error_message = str(e)
                    repo.save(article)
                    continue

                if result is None:
                    article.status = "failed"
                    article.error_message = "Scrape returned None"
                    repo.save(article)
                    continue

                # 生成摘要
                md_content = Path(result["markdown_path"]).read_text(encoding="utf-8")
                summary = summarizer.summarize(md_content)

                # 存储
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
            notifier = _create_notifier(config)
            if notifier:
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
