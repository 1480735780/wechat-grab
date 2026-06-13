import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Optional

import feedparser
import requests

from app.models import Article, Alert, FetchResult, Subscription

logger = logging.getLogger("wechat-article")


def fetch_feed(
    subscription: Subscription,
    base_url: str = "http://localhost:1200",
    timeout: int = 30,
) -> list[Article]:
    url = f"{base_url}{subscription.rss_path}"
    logger.info(f"Fetching RSS feed: {url}")

    try:
        session = requests.Session()
        session.trust_env = False
        response = session.get(
            url,
            timeout=timeout,
            headers={"User-Agent": "WeChatArticleMonitor/1.0"},
        )
        response.encoding = "utf-8"
        feed = feedparser.parse(response.text)

        if feed.bozo and not feed.entries:
            logger.warning(f"Failed to parse feed from {url}: {feed.bozo_exception}")
            return []

        articles = []
        for entry in feed.entries:
            publish_time = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                publish_time = datetime(*entry.published_parsed[:6])
            elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                publish_time = datetime(*entry.updated_parsed[:6])

            article = Article(
                title=getattr(entry, "title", "无标题"),
                article_url=getattr(entry, "link", ""),
                author=subscription.name,
                publish_time=publish_time,
            )
            if article.article_url:
                articles.append(article)

        logger.info(f"Found {len(articles)} articles from {subscription.name}")
        return articles

    except Exception as e:
        logger.error(f"Error fetching feed {url}: {e}")
        return []


def fetch_mp_articles(
    subscription: Subscription,
    cookie: str,
    token: str,
    count: int = 5,
) -> tuple[list[Article], Optional[Alert]]:
    """通过微信公众平台接口获取公众号文章列表

    Returns:
        (articles, alert): 文章列表和可能的告警（Cookie 过期时）
    """
    biz = subscription.rss_path.replace("/wechat/mp/", "")
    url = "https://mp.weixin.qq.com/cgi-bin/appmsg"
    params = {
        "action": "list_ex",
        "begin": "0",
        "count": str(count),
        "fakeid": biz,
        "type": "9",
        "query": "",
        "token": token,
        "lang": "zh_CN",
        "f": "json",
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Cookie": cookie,
        "Referer": "https://mp.weixin.qq.com/",
    }

    logger.info(f"Fetching MP articles for: {subscription.name} (biz={biz})")

    try:
        session = requests.Session()
        session.trust_env = False
        resp = session.get(url, headers=headers, params=params, timeout=15)
        data = resp.json()

        # 检测 Cookie 过期
        ret = data.get("ret", data.get("base_resp", {}).get("ret", 0))
        if ret != 0:
            logger.error(f"MP API returned error for {subscription.name}: ret={ret}, msg={data.get('msg', '')}")
            alert = Alert(
                key="COOKIE_EXPIRED",
                title="MP API Cookie 已失效",
                message=f"公众号 {subscription.name} 返回错误码 {ret}",
                level="error",
                error_code=ret,
            )
            return [], alert

        if "app_msg_list" not in data:
            logger.warning(f"No articles returned for {subscription.name}: {data.get('base_resp', {})}")
            return [], None

        articles = []
        for item in data["app_msg_list"]:
            publish_time = None
            update_time = item.get("update_time")
            if update_time:
                publish_time = datetime.fromtimestamp(update_time)

            article = Article(
                title=item.get("title", "无标题"),
                article_url=item.get("link", ""),
                author=subscription.name,
                publish_time=publish_time,
            )
            if article.article_url:
                articles.append(article)

        logger.info(f"Found {len(articles)} articles from {subscription.name} via MP API")
        return articles, None

    except Exception as e:
        logger.error(f"Error fetching MP articles for {subscription.name}: {e}")
        return [], None


def fetch_all_feeds(
    subscriptions: list[Subscription],
    base_url: str = "http://localhost:1200",
    timeout: int = 30,
    max_workers: int = 5,
    mp_cookie: str = "",
    mp_token: str = "",
) -> FetchResult:
    """获取所有订阅源的文章，MP API 优先，RSSHub 降级

    Returns:
        FetchResult: 包含文章列表和告警列表
    """
    result = FetchResult()
    use_mp = bool(mp_cookie and mp_token)
    mp_success = False

    if use_mp:
        # 尝试使用微信公众平台接口
        for sub in subscriptions:
            articles, alert = fetch_mp_articles(sub, mp_cookie, mp_token)
            if alert:
                result.alerts.append(alert)
            if articles:
                mp_success = True
            result.articles.extend(articles)
            time.sleep(1)  # 避免请求过快

    # 如果 MP API 未使用或失败，尝试 RSSHub
    if not mp_success:
        rsshub_articles_count = 0
        try:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_sub = {
                    executor.submit(fetch_feed, sub, base_url, timeout): sub
                    for sub in subscriptions
                }

                for future in as_completed(future_to_sub):
                    sub = future_to_sub[future]
                    try:
                        articles = future.result()
                        rsshub_articles_count += len(articles)
                        result.articles.extend(articles)
                    except Exception as e:
                        logger.error(f"Error processing feed for {sub.name}: {e}")
        except Exception as e:
            logger.error(f"RSSHub fetch failed: {e}")

        # 如果 RSSHub 也返回空，生成告警
        if rsshub_articles_count == 0 and subscriptions:
            logger.warning("RSSHub returned no articles from any subscription")
            result.alerts.append(Alert(
                key="RSSHUB_UNREACHABLE",
                title="RSSHub 服务不可达",
                message=f"所有订阅源均无法获取文章，RSSHub 地址：{base_url}",
                level="error",
            ))

    logger.info(f"Total articles found: {len(result.articles)}")
    return result
