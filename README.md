# 微信公众号监控助手

自动检测微信公众号更新 → 抓取文章 → 转换为 Markdown → 邮件/飞书推送日报

> 微信公众号监控助手 | 定时抓取文章、自动转 Markdown、邮件日报推送。一键安装，支持本地/守护/云部署三种模式。

## 🎬 功能演示

查看动画演示：[👉 点击查看项目介绍动画](https://raw.githubusercontent.com/1480735780/wechat-grab/main/video/index.html)

## ✨ 功能

- ⏰ **定时检测**: 自动监控公众号更新（支持自定义时间段）
- 📄 **自动抓取**: 抓取文章并转换为 Markdown 格式
- 🖼️ **图片本地化**: 自动下载图片到本地并替换链接
- 📧 **邮件推送**: 每日文章汇总推送到邮箱
- 🔒 **Cookie 过期提醒**: 自动检测并邮件提醒
- 🐳 **Docker 部署**: 一键部署到云服务器

## 🚀 快速开始

### 一键安装

```bash
curl -fsSL https://raw.githubusercontent.com/1480735780/wechat-grab/main/install.sh | bash
```

### 配置

```bash
cd ~/wechat-grab
./wechat-monitor setup
```

### 运行

```bash
# 本地模式：立即抓取一次（测试用）
./wechat-monitor run

# 守护模式：后台持续运行（自动检测）
./wechat-monitor daemon
```

## 📋 所有命令

| 命令 | 说明 |
|------|------|
| `./wechat-monitor setup` | 交互式配置向导 |
| `./wechat-monitor run` | 运行一次同步任务 |
| `./wechat-monitor daemon` | 启动守护进程 |
| `./wechat-monitor status` | 查看运行状态 |
| `./wechat-monitor logs` | 查看实时日志 |
| `./wechat-monitor stop` | 停止守护进程 |
| `./wechat-monitor deploy` | 引导 Docker 部署 |

## 🏗️ 三种使用模式

### 模式 1：本地模式（免费，按需运行）

适合偶尔抓取，不需要 24 小时监控：
- 打开终端运行 `./wechat-monitor run`
- 立即抓取一次后退出
- 适合手动触发

### 模式 2：守护模式（离线自动运行）

适合需要持续自动监控：
- 运行 `./wechat-monitor daemon`
- 后台持续运行，按配置自动检测
- 关闭终端也不停
- 需要本地电脑一直开机

### 模式 3：云服务器部署（推荐，24/7 运行）

适合需要真正的全天候自动监控：
- 运行 `./wechat-monitor deploy` 引导部署
- 部署到云服务器，关机也能运行
- 需要云服务器和 Docker

## 📁 项目结构

```
├── app/              # 核心业务逻辑
│   ├── config.py     # 配置管理
│   ├── fetcher.py    # 文章获取（MP API + RSSHub）
│   ├── scraper.py    # HTML→Markdown 转换
│   ├── repository.py # SQLite 数据库操作
│   ├── scheduler.py  # 定时任务逻辑
│   ├── summarizer.py # 摘要生成
│   ├── models.py     # 数据模型
│   ├── logger.py     # 日志配置
│   └── notifier/     # 通知模块
│       ├── email.py  # 邮件通知
│       └── base.py   # 通知基类
├── tools/            # 辅助工具
│   └── query_biz.py  # 公众号 biz 查询
├── video/            # 动画演示
├── tests/            # 单元测试
├── cli.py            # 命令行工具
├── main.py           # 主入口（守护模式）
├── install.sh        # 一键安装脚本
├── config.yaml.example # 配置模板
├── .env.example      # 环境变量模板
├── Dockerfile        # Docker 镜像
├── docker-compose.yml # Docker 编排
└── requirements.txt  # Python 依赖
```

## 🔧 手动安装（不用一键脚本）

```bash
# 1. 克隆项目
git clone https://github.com/1480735780/wechat-grab.git
cd wechat-grab

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置
cp config.yaml.example config.yaml
cp .env.example .env
# 编辑 config.yaml 和 .env 填写配置

# 4. 运行
python cli.py setup    # 或手动编辑配置
python cli.py run      # 测试
python cli.py daemon   # 守护进程
```

## 🔑 获取必要配置

### MP Cookie 和 Token

1. 登录微信公众平台后台 https://mp.weixin.qq.com/
2. 按 F12 打开开发者工具
3. 切换到 Network 标签
4. 刷新页面
5. 点击任意请求，找到 Cookie 和 Token
6. 复制到 `.env` 文件

### QQ 邮箱 SMTP 授权码

1. 登录 QQ 邮箱
2. 设置 → 账户 → POP3/SMTP 服务
3. 开启服务并生成授权码
4. 复制到 `.env` 文件的 `EMAIL_PASSWORD`

## 🐳 Docker 部署

```bash
# 1. 准备 .env 文件
cp .env.example .env
# 编辑 .env 填写敏感信息

# 2. 启动
docker compose up -d --build

# 3. 查看日志
docker compose logs -f
```

## ⚠️ 注意事项

1. **MP Cookie 会过期**：通常 2-4 小时，过期后会自动发邮件提醒
2. **隐私保护**：`.env` 和 `config.yaml` 已加入 `.gitignore`，不会上传到 Git
3. **首次运行**：建议先用 `run` 命令测试，确认配置正确后再启动 `daemon`

## 📄 License

MIT
