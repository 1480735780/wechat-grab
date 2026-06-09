import logging
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import load_config
from app.logger import setup_logger
from app.scheduler import create_sync_job, create_digest_job


def main():
    config = load_config()
    logger = setup_logger()
    logger.info("WeChat Article Monitor starting...")

    scheduler = BlockingScheduler()

    # Job1: 文章同步 (8:00-22:00, 每小时)
    sync_config = config.scheduler.sync
    sync_job = create_sync_job(config)
    scheduler.add_job(
        sync_job,
        trigger=CronTrigger(
            hour=f"{sync_config.start_hour}-{sync_config.end_hour}",
            minute=0,
        ),
        id="sync_job",
        max_instances=1,
        coalesce=True,
    )
    logger.info(
        f"Sync job scheduled: {sync_config.start_hour}:00-{sync_config.end_hour}:00, every hour"
    )

    # Job2: 日报推送 (每天 22:05)
    digest_config = config.scheduler.digest
    digest_job = create_digest_job(config)
    scheduler.add_job(
        digest_job,
        trigger=CronTrigger(
            hour=digest_config.hour,
            minute=digest_config.minute,
        ),
        id="digest_job",
        max_instances=1,
        coalesce=True,
    )
    logger.info(f"Digest job scheduled: daily at {digest_config.hour}:{digest_config.minute:02d}")

    # 启动时立即执行一次同步
    if sync_config.run_on_startup:
        logger.info("Run on startup enabled, executing sync job immediately")
        sync_job()

    try:
        logger.info("Scheduler started, waiting for jobs...")
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler shutting down")


if __name__ == "__main__":
    main()
