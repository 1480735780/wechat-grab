import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Optional

import feedparser
import requests

from app.models import Article, Subscription

logger = logging.getLogger("wechat-article")


def fetch_feed(
    subscription: Subscription,
    base_url: str = "https://rsshub.app",
    timeout: int = 30,
) -> list[Article]:
    url = f"{base_url}{subscription.rss_path}"
    logger.info(f"Fetching RSS feed: {url}")

    try:
        response = requests.get(
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
) -> tuple[list[Article], bool]:
    """通过微信公众平台接口获取公众号文章列表

    Returns:
        (articles, cookie_expired): 文章列表和 Cookie 是否过期标志
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
        resp = requests.get(url, headers=headers, params=params, timeout=15)
        data = resp.json()

        # 检测 Cookie 过期：ret != 0 或 base_resp.ret != 0
        ret = data.get("ret", data.get("base_resp", {}).get("ret", 0))
        if ret != 0:
            logger.error(f"MP API returned error for {subscription.name}: ret={ret}, msg={data.get('msg', '')}")
            # ret=200013 通常表示 token/cookie 过期
            return [], True

        if "app_msg_list" not in data:
            logger.warning(f"No articles returned for {subscription.name}: {data.get('base_resp', {})}")
            return [], False

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
        return articles, False

    except Exception as e:
        logger.error(f"Error fetching MP articles for {subscription.name}: {e}")
        return [], False


def fetch_all_feeds(
    subscriptions: list[Subscription],
    base_url: str = "https://rsshub.app",
    timeout: int = 30,
    max_workers: int = 5,
    mp_cookie: str = "",
    mp_token: str = "",
) -> tuple[list[Article], bool]:
    """获取所有订阅源的文章

    Returns:
        (articles, cookie_expired): 文章列表和 Cookie 是否过期标志
    """
    all_articles = []
    cookie_expired = False

    use_mp = bool(mp_cookie and mp_token)

    if use_mp:
        # 使用微信公众平台接口（更可靠，但需要 Cookie）
        for sub in subscriptions:
            articles, expired = fetch_mp_articles(sub, mp_cookie, mp_token)
            all_articles.extend(articles)
            if expired:
                cookie_expired = True
            time.sleep(1)  # 避免请求过快
    else:
        # 使用 RSSHub（无需 Cookie，但可能不稳定）
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_sub = {
                executor.submit(fetch_feed, sub, base_url, timeout): sub
                for sub in subscriptions
            }

            for future in as_completed(future_to_sub):
                sub = future_to_sub[future]
                try:
                    articles = future.result()
                    all_articles.extend(articles)
                except Exception as e:
                    logger.error(f"Error processing feed for {sub.name}: {e}")

    logger.info(f"Total articles found: {len(all_articles)}")
    return all_articles, cookie_expired
