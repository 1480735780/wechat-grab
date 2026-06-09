# WeChat Article Monitor — 设计文档

## 概述

一个自动监控微信公众号文章更新的个人知识管理工具。通过 RSSHub 获取公众号更新，自动抓取文章并转换为 Markdown（含图片本地化），推送到邮箱或飞书云空间。

**技术选型**：Python + RSSHub + APScheduler + SQLite + SMTP + 飞书开放平台

**架构方案**：单进程 + APScheduler（方案 A）

---

## 项目结构

```
wechat-article/
├── config.yaml              # 主配置文件
├── .env.example             # 环境变量模板
├── main.py                  # 入口：启动 APScheduler
├── app/
│   ├── __init__.py
│   ├── config.py            # Pydantic 配置模型，支持环境变量覆盖
│   ├── models.py            # 数据模型定义
│   ├── scheduler.py         # APScheduler 调度逻辑
│   ├── fetcher.py           # RSSHub 轮询与文章发现
│   ├── scraper.py           # 文章抓取 + 图片下载 + HTML→Markdown
│   ├── repository.py        # SQLite 去重与状态管理
│   ├── summarizer.py        # 摘要生成抽象层
│   ├── logger.py            # 统一日志配置
│   └── notifier/            # 推送模块
│       ├── __init__.py
│       ├── base.py          # Notifier 抽象基类
│       ├── email.py         # SMTP 邮件推送（日报模式）
│       └── feishu.py        # 飞书推送（第二阶段）
├── output/                  # Markdown 文件输出目录
│   └── {公众号名}/{年}/{月}/
│       ├── {文章标题}.md
│       └── images/          # 文章图片本地存储
├── data/
│   └── articles.db          # SQLite 数据库
├── logs/
│   └── app.log              # 应用日志
├── requirements.txt
├── Dockerfile
└── docker-compose.yml       # 包含 RSSHub + 本应用
```

---

## 核心流程

### Job1：文章同步（8:00-22:00，每60分钟）

```
APScheduler CronTrigger: 0 8-22 * * *
run_on_startup=true（仅触发同步，不触发日报）
max_instances=1, coalesce=True
  │
  ├─→ fetcher: 并发轮询 RSSHub 获取各公众号最新文章列表
  │     ThreadPoolExecutor(max_workers=5)
  │
  ├─→ repository: 查询 SQLite，过滤已抓取文章
  │     以 article_url 为唯一键去重
  │
  ├─→ scraper: 对新文章执行：
  │     1. 抓取原文 HTML
  │     2. 下载图片到 output/{公众号}/{年}/{月}/images/
  │     3. 替换 HTML 中的图片链接为本地相对路径
  │     4. HTML → Markdown
  │     5. 在文档头部写入 frontmatter 元信息（含 tags、content_hash）
  │     6. 计算 content_hash = md5(markdown_content)
  │     7. 保存 .md 文件
  │
  ├─→ repository: 写入 SQLite 记录
  │
  └─→ summarizer: 生成摘要（第一版：截取前200字），存入数据库
```

### Job2：日报推送（每天 22:05）

```
APScheduler CronTrigger: 5 22 * * *
  │
  ├─→ repository: 查询当日 status=fetched 且未通知的文章
  │
  ├─→ 无新文章 → 跳过，不发空邮件
  │
  └─→ notifier: 发送日报邮件
        主题：微信公众号文章日报 - {日期}
        内容：文章标题 + 来源 + 摘要 + 原文链接
        附件：所有 Markdown 文件
        发送成功 → 批量更新 status=notified
```

---

## 配置模型

### config.yaml

```yaml
# RSSHub 配置
rsshub:
  base_url: "https://rsshub.app"    # 公共实例，可改为自部署地址
  timeout: 30

# 订阅的公众号列表
subscriptions:
  - name: "机器之心"
    rss_path: "/wechat/mp/almosthuman2014"
  - name: "腾讯技术工程"
    rss_path: "/wechat/mp/tencent_tech"
  - name: "InfoQ"
    rss_path: "/wechat/mp/infoqchina"

# 调度配置
scheduler:
  sync:
    start_hour: 8
    end_hour: 22
    interval_minutes: 60
    run_on_startup: true               # Docker 启动后立即执行一次同步
  digest:
    hour: 22
    minute: 5                          # 日报推送时间

# 输出配置
output:
  base_dir: "./output"
  organize_by_date: true              # 按年/月组织目录

# 推送配置
notifier:
  email:
    enabled: true
    smtp_host: "smtp.gmail.com"
    smtp_port: 587
    use_tls: true
    sender: "xxx@gmail.com"
    # password 仅通过环境变量 WA_NOTIFIER_EMAIL_PASSWORD 设置
    recipients:
      - "your@email.com"
    digest_mode: true                 # 日报模式：每天一封汇总邮件
  feishu:
    enabled: false                    # 第二阶段启用
    app_id: ""
    app_secret: ""
    folder_token: ""

# 数据库
database:
  path: "./data/articles.db"
```

### 环境变量覆盖

使用 Pydantic BaseSettings，环境变量前缀 `WA_`：

| 环境变量 | 覆盖字段 |
|---------|---------|
| `WA_RSSHUB_BASE_URL` | `rsshub.base_url` |
| `WA_NOTIFIER_EMAIL_PASSWORD` | 邮件密码（仅环境变量，不写入配置文件） |
| `WA_DATABASE_PATH` | `database.path` |

---

## 数据模型

### SQLite — articles 表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增主键 |
| article_url | TEXT UNIQUE | 文章原文链接，唯一索引 |
| title | TEXT | 文章标题 |
| author | TEXT | 来源公众号 |
| publish_time | DATETIME | 发布时间 |
| fetched_at | DATETIME | 抓取时间 |
| status | TEXT | pending / fetched / notified / failed / permanent_failed |
| markdown_path | TEXT | 本地 Markdown 文件路径 |
| content_hash | TEXT | md5(markdown_content)，检测内容变更 |
| error_message | TEXT NULL | 失败时的错误信息 |
| fail_count | INTEGER DEFAULT 0 | 连续失败次数 |
| created_at | DATETIME | 记录创建时间 |

### 去重策略

- 以 `article_url` 为唯一键：存在则跳过
- 以 `content_hash` 检测内容变更：同一 URL 但 hash 不同 → 标记为 updated
- Dead-letter 机制：`fail_count > 5` → `status=permanent_failed`，不再重试

---

## 核心模块设计

### fetcher.py — RSS 轮询

- 使用 `feedparser` 解析 RSS feed
- URL 拼接：`base_url + rss_path`
- 并发请求：`ThreadPoolExecutor(max_workers=5)`
- 重试机制：最多 3 次，指数退避
- 单个订阅源失败不影响其他源

### scraper.py — 抓取与转换

- `requests` 获取文章 HTML
- `BeautifulSoup` 提取正文区域
- 遍历 `<img>` 标签：下载图片 → 替换 src 为本地相对路径
- 图片下载失败时保留原链接，不阻塞流程
- `markdownify` 或 `html2text` 进行 HTML → Markdown 转换
- Markdown 头部 frontmatter：

```markdown
---
title: "文章标题"
author: "公众号名称"
published: "2026-06-08 10:30"
source: "https://mp.weixin.qq.com/..."
tags:
  - wechat
content_hash: "xxxxx"
---

正文内容...
```

- 文件名：发布日期 + 标题 slug 化
- 计算 `content_hash = md5(markdown_content)`

### repository.py — 数据持久化

```python
class ArticleRepository:
    def exists_by_url(article_url: str) -> bool
    def get_by_url(article_url: str) -> Article | None
    def save(article: Article) -> int
    def update_status(article_id: int, status: str)
    def increment_fail_count(article_id: int)
    def check_content_changed(article_url: str, new_hash: str) -> bool
    def get_pending_notifications() -> list[Article]       # 获取待推送文章
    def get_articles_by_date(date: date) -> list[Article]  # 获取某日文章（日报用）
```

- 启动时自动建表（如果不存在）
- SQLite 写入失败：记录 error，保留文件，下次重试写库

### summarizer.py — 摘要生成

```python
class BaseSummarizer(ABC):
    @abstractmethod
    def summarize(self, markdown_content: str) -> str

class TruncateSummarizer(BaseSummarizer):
    """第一版：截取前 200 字"""
    def summarize(self, markdown_content: str) -> str:
        return markdown_content[:200]

# 未来可扩展：
# class DeepSeekSummarizer(BaseSummarizer): ...
# class GPTSummarizer(BaseSummarizer): ...
```

### notifier/ — 推送模块

```python
# base.py
class BaseNotifier(ABC):
    @abstractmethod
    def send(self, articles: list[Article], summaries: list[str]) -> bool

# email.py — 日报模式
class EmailNotifier(BaseNotifier):
    def send(self, articles, summaries) -> bool:
        """
        每天一封汇总邮件：
        主题：微信公众号文章日报 - {日期}
        内容：
          1. 文章标题 + 来源
          2. 摘要
          3. 原文链接
        附件：所有 Markdown 文件
        """
```

- 日报模式：每天一封汇总邮件，而非逐篇发送
- SMTP 限流保护：发送间隔 1 秒
- 发送失败标记 status=failed，下次调度重试

### scheduler.py — 调度

两个独立 Job，职责分离：

**Job1：文章同步**
- CronTrigger：`0 8-22 * * *`（8:00-22:00 每小时）
- `max_instances=1` + `coalesce=True`：防止任务重叠
- `run_on_startup=true`：Docker 启动后立即执行一次同步（不触发日报）

**Job2：日报推送**
- CronTrigger：`5 22 * * *`（每天 22:05）
- 查询当日 status=fetched 且未通知的文章
- 无新文章则跳过，不发空邮件
- 发送成功后批量更新 status=notified

### logger.py — 日志

- Console + File 双输出
- 文件输出：`logs/app.log`，按天轮转，保留 30 天
- 格式：`{time} | {level} | {module} | {message}`

---

## 部署

### Docker Compose

```yaml
services:
  rsshub:
    image: diygod/rsshub:latest
    ports:
      - "1200:1200"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:1200/healthz"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped

  wechat-article:
    build: .
    environment:
      - WA_RSSHUB_BASE_URL=http://rsshub:1200
      - WA_NOTIFIER_EMAIL_PASSWORD=${EMAIL_PASSWORD}
    volumes:
      - ./output:/app/output
      - ./data:/app/data
      - ./logs:/app/logs
      - ./config.yaml:/app/config.yaml:ro
    depends_on:
      rsshub:
        condition: service_healthy
    restart: unless-stopped
```

- RSSHub 和应用在同一 compose 网络中，应用通过内网访问 RSSHub
- output/data/logs 挂载到宿主机，持久化数据
- config.yaml 只读挂载
- RSSHub healthcheck 确保服务就绪后再启动应用

---

## 错误处理

| 场景 | 处理方式 |
|------|---------|
| RSSHub 请求超时/失败 | 重试 3 次（指数退避），跳过该订阅源，记录日志 |
| 文章 HTML 抓取失败 | 标记 status=failed，记录 error_message，下次调度重试 |
| 图片下载失败 | 保留原链接，不阻塞，日志 warning |
| SQLite 写入失败 | 记录 error，保留文件，下次重试写库 |
| SMTP 发送失败 | 标记 status=failed，下次调度重试 |
| 连续失败 > 5 次 | 标记 status=permanent_failed，不再重试（dead-letter） |
| APScheduler 任务重叠 | max_instances=1 + coalesce=True，自动跳过 |

---

## 分阶段实施

### 第一阶段：核心链路验证

- RSSHub 轮询 + 文章发现
- 文章抓取 + HTML→Markdown + 图片本地化
- SQLite 去重
- 邮件日报推送
- Docker 部署

### 第二阶段：飞书集成

- 飞书开放平台接入
- 自动创建文档并上传 Markdown
- 飞书消息通知

### 未来扩展

- AI 摘要（DeepSeek / GPT / Claude）
- RAG 知识库（LangChain + Qdrant + BGE-M3 Embedding）
- Web 管理界面
- 数据库迁移到 PostgreSQL
