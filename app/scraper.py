import hashlib
import logging
import os
import re
import time
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as md

logger = logging.getLogger("wechat-article")


def slugify(text: str, max_length: int = 50) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", "-", text).strip("-")
    if len(text) > max_length:
        text = text[:max_length].rstrip("-")
    return text or "untitled"


def _download_image(img_url: str, save_dir: str) -> Optional[str]:
    try:
        response = requests.get(img_url, timeout=15, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        if response.status_code != 200:
            logger.warning(f"Failed to download image: {img_url}")
            return None

        filename = img_url.split("/")[-1].split("?")[0]
        if not filename or "." not in filename:
            ext = ".jpg"
            content_type = response.headers.get("Content-Type", "")
            if "png" in content_type:
                ext = ".png"
            elif "gif" in content_type:
                ext = ".gif"
            elif "webp" in content_type:
                ext = ".webp"
            filename = hashlib.md5(img_url.encode()).hexdigest()[:12] + ext

        save_path = os.path.join(save_dir, filename)
        # 避免文件名冲突：如果已存在则加 hash 前缀
        if os.path.exists(save_path):
            name, ext = os.path.splitext(filename)
            filename = f"{hashlib.md5(img_url.encode()).hexdigest()[:8]}_{name}{ext}"
            save_path = os.path.join(save_dir, filename)
        with open(save_path, "wb") as f:
            f.write(response.content)

        logger.debug(f"Downloaded image: {img_url} -> {save_path}")
        return filename

    except Exception as e:
        logger.warning(f"Error downloading image {img_url}: {e}")
        return None


def scrape_article(
    article_url: str,
    author: str,
    output_base_dir: str = "./output",
    organize_by_date: bool = True,
    publish_time: Optional[datetime] = None,
) -> Optional[dict]:
    logger.info(f"Scraping article: {article_url}")

    # 重试机制：最多 3 次，指数退避
    max_retries = 3
    response = None
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(
                article_url,
                timeout=30,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                },
            )
            response.encoding = "utf-8"
            if response.status_code == 200:
                break
            logger.warning(f"Attempt {attempt}/{max_retries}: status {response.status_code} for {article_url}")
        except Exception as e:
            logger.warning(f"Attempt {attempt}/{max_retries} failed for {article_url}: {e}")

        if attempt < max_retries:
            wait = 2 ** attempt  # 指数退避：2s, 4s
            logger.info(f"Retrying in {wait}s...")
            time.sleep(wait)

    if response is None or response.status_code != 200:
        logger.error(f"Failed to fetch article after {max_retries} attempts: {article_url}")
        return None

    soup = BeautifulSoup(response.text, "html.parser")

    title_el = soup.find("h1", id="activity-name") or soup.find("h1")
    title = title_el.get_text(strip=True) if title_el else "无标题"

    content_el = soup.find("div", id="js_content") or soup.find("article") or soup.find("body")
    if not content_el:
        logger.error(f"Cannot find article content: {article_url}")
        return None

    now = publish_time or datetime.now()
    if organize_by_date:
        article_dir = Path(output_base_dir) / author / str(now.year) / f"{now.month:02d}"
    else:
        article_dir = Path(output_base_dir) / author
    article_dir.mkdir(parents=True, exist_ok=True)

    images_dir = article_dir / "images"
    images_dir.mkdir(exist_ok=True)

    for img in content_el.find_all("img"):
        src = img.get("data-src") or img.get("src", "")
        if not src:
            continue
        if src.startswith("//"):
            src = "https:" + src

        local_filename = _download_image(src, str(images_dir))
        if local_filename:
            img["src"] = f"images/{local_filename}"
            if img.get("data-src"):
                del img["data-src"]
        else:
            logger.warning(f"Keeping original image URL: {src}")

    markdown_content = md(str(content_el), heading_style="ATX", strip=["script", "style"])

    # 先计算正文的 content_hash（不含 frontmatter 中的 hash 字段本身）
    body_hash = hashlib.md5(markdown_content.strip().encode("utf-8")).hexdigest()

    frontmatter = f"""---
title: "{title}"
author: "{author}"
published: "{now.strftime('%Y-%m-%d %H:%M')}"
source: "{article_url}"
tags:
  - wechat
content_hash: "{body_hash}"
---

"""

    full_markdown = frontmatter + markdown_content.strip() + "\n"

    filename = f"{now.strftime('%Y%m%d')}-{slugify(title)}.md"
    # 避免文件名冲突：如果已存在则加序号
    markdown_path = article_dir / filename
    if markdown_path.exists():
        counter = 1
        while (article_dir / f"{now.strftime('%Y%m%d')}-{slugify(title)}-{counter}.md").exists():
            counter += 1
        filename = f"{now.strftime('%Y%m%d')}-{slugify(title)}-{counter}.md"
        markdown_path = article_dir / filename

    markdown_path.write_text(full_markdown, encoding="utf-8")

    logger.info(f"Article saved: {markdown_path}")

    return {
        "markdown_path": str(markdown_path),
        "content_hash": body_hash,
        "title": title,
    }
