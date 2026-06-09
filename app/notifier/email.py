import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from app.models import Article
from app.notifier.base import BaseNotifier

logger = logging.getLogger("wechat-article")


class EmailNotifier(BaseNotifier):
    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        use_tls: bool,
        sender: str,
        password: str,
        recipients: list[str],
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.use_tls = use_tls
        self.sender = sender
        self.password = password
        self.recipients = recipients

    def send(self, articles: list[Article], summaries: list[str]) -> bool:
        if not articles:
            logger.info("No articles to notify, skipping email")
            return False

        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        subject = f"微信公众号文章日报 - {today}"

        body_parts = [f"<h2>微信公众号文章日报 - {today}</h2>"]
        for i, (article, summary) in enumerate(zip(articles, summaries), 1):
            body_parts.append(
                f'<h3>{i}. {article.title}</h3>'
                f'<p><strong>来源：</strong>{article.author}</p>'
                f'<p><strong>摘要：</strong>{summary}</p>'
                f'<p><a href="{article.article_url}">阅读原文</a></p>'
                f'<hr>'
            )

        html_body = "\n".join(body_parts)

        msg = MIMEMultipart()
        msg["Subject"] = subject
        msg["From"] = self.sender
        msg["To"] = ", ".join(self.recipients)
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        for article in articles:
            if article.markdown_path and Path(article.markdown_path).exists():
                with open(article.markdown_path, "r", encoding="utf-8") as f:
                    md_content = f.read()
                md_attachment = MIMEText(md_content, "plain", "utf-8")
                filename = Path(article.markdown_path).name
                md_attachment.add_header(
                    "Content-Disposition", "attachment", filename=filename
                )
                msg.attach(md_attachment)

        try:
            if self.use_tls:
                with smtplib.SMTP(self.smtp_host, self.smtp_port) as smtp:
                    smtp.starttls()
                    smtp.login(self.sender, self.password)
                    smtp.sendmail(self.sender, self.recipients, msg.as_string())
            else:
                with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port) as smtp:
                    smtp.login(self.sender, self.password)
                    smtp.sendmail(self.sender, self.recipients, msg.as_string())
            logger.info(f"Digest email sent: {len(articles)} articles")
            return True
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False
