import hashlib
import logging
import os
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

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
        session = requests.Session()
        session.trust_env = False
        response = session.get(img_url, timeout=15, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        if response.status_code != 200:
            logger.warning(f"Failed to download image: {img_url}")
            return None

        # 从 URL 或 Content-Disposition 提取文件名
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

    try:
        session = requests.Session()
        session.trust_env = False
        response = session.get(
            article_url,
            timeout=30,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
        )
        response.encoding = "utf-8"
        if response.status_code != 200:
            logger.error(f"Failed to fetch article: {response.status_code}")
            return None

    except Exception as e:
        logger.error(f"Error fetching article {article_url}: {e}")
        return None

    soup = BeautifulSoup(response.text, "html.parser")

    # 提取标题
    title_el = soup.find("h1", id="activity-name") or soup.find("h1")
    title = title_el.get_text(strip=True) if title_el else "无标题"

    # 提取正文
    content_el = soup.find("div", id="js_content") or soup.find("article") or soup.find("body")
    if not content_el:
        logger.error(f"Cannot find article content: {article_url}")
        return None

    # 构建输出目录
    now = publish_time or datetime.now()
    if organize_by_date:
        article_dir = Path(output_base_dir) / author / str(now.year) / f"{now.month:02d}"
    else:
        article_dir = Path(output_base_dir) / author
    article_dir.mkdir(parents=True, exist_ok=True)

    images_dir = article_dir / "images"
    images_dir.mkdir(exist_ok=True)

    # 下载图片并替换链接
    for img in content_el.find_all("img"):
        src = img.get("data-src") or img.get("src", "")
        if not src:
            continue
        if src.startswith("//"):
            src = "https:" + src

        local_filename = _download_image(src, str(images_dir))
        if local_filename:
            img["src"] = f"images/{local_filename}"
            # 清除 data-src 避免重复
            if img.get("data-src"):
                del img["data-src"]
        else:
            logger.warning(f"Keeping original image URL: {src}")

    # HTML -> Markdown
    markdown_content = md(str(content_el), heading_style="ATX", strip=["script", "style"])

    # 构建 frontmatter
    frontmatter = f"""---
title: "{title}"
author: "{author}"
published: "{now.strftime('%Y-%m-%d %H:%M')}"
source: "{article_url}"
tags:
  - wechat
---

"""

    full_markdown = frontmatter + markdown_content.strip() + "\n"

    # 计算 content_hash
    content_hash = hashlib.md5(full_markdown.encode("utf-8")).hexdigest()

    # 更新 frontmatter 中的 content_hash
    full_markdown = full_markdown.replace(
        'tags:\n  - wechat\n---',
        f'tags:\n  - wechat\ncontent_hash: "{content_hash}"\n---',
    )

    # 保存文件
    filename = f"{now.strftime('%Y%m%d')}-{slugify(title)}.md"
    markdown_path = article_dir / filename
    markdown_path.write_text(full_markdown, encoding="utf-8")

    logger.info(f"Article saved: {markdown_path}")

    return {
        "markdown_path": str(markdown_path),
        "content_hash": content_hash,
        "title": title,
    }
