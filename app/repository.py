import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from app.models import Article


class ArticleRepository:
    def __init__(self, db_path: str = "./data/articles.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article_url TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL DEFAULT '',
                author TEXT NOT NULL DEFAULT '',
                publish_time DATETIME,
                fetched_at DATETIME,
                status TEXT NOT NULL DEFAULT 'pending',
                markdown_path TEXT NOT NULL DEFAULT '',
                content_hash TEXT NOT NULL DEFAULT '',
                summary TEXT NOT NULL DEFAULT '',
                error_message TEXT,
                fail_count INTEGER NOT NULL DEFAULT 0,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_article_url ON articles(article_url)"
        )
        conn.commit()
        conn.close()

    def _row_to_article(self, row: sqlite3.Row) -> Article:
        return Article(
            id=row["id"],
            article_url=row["article_url"],
            title=row["title"],
            author=row["author"],
            publish_time=datetime.fromisoformat(row["publish_time"])
            if row["publish_time"]
            else None,
            fetched_at=datetime.fromisoformat(row["fetched_at"])
            if row["fetched_at"]
            else None,
            status=row["status"],
            markdown_path=row["markdown_path"],
            content_hash=row["content_hash"],
            summary=row["summary"],
            error_message=row["error_message"],
            fail_count=row["fail_count"],
            created_at=datetime.fromisoformat(row["created_at"])
            if row["created_at"]
            else None,
        )

    def exists_by_url(self, article_url: str) -> bool:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT 1 FROM articles WHERE article_url = ?", (article_url,)
        ).fetchone()
        conn.close()
        return row is not None

    def get_by_url(self, article_url: str) -> Optional[Article]:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM articles WHERE article_url = ?", (article_url,)
        ).fetchone()
        conn.close()
        if row is None:
            return None
        return self._row_to_article(row)

    def save(self, article: Article) -> int:
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                """INSERT INTO articles
                   (article_url, title, author, publish_time, fetched_at, status,
                    markdown_path, content_hash, summary, error_message, fail_count)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    article.article_url,
                    article.title,
                    article.author,
                    article.publish_time.isoformat() if article.publish_time else None,
                    article.fetched_at.isoformat() if article.fetched_at else None,
                    article.status,
                    article.markdown_path,
                    article.content_hash,
                    article.summary,
                    article.error_message,
                    article.fail_count,
                ),
            )
            conn.commit()
            article_id = cursor.lastrowid
        except sqlite3.IntegrityError:
            # article_url 已存在，执行更新
            conn.execute(
                """UPDATE articles SET
                   title = ?, author = ?, publish_time = ?, fetched_at = ?, status = ?,
                   markdown_path = ?, content_hash = ?, summary = ?,
                   error_message = ?, fail_count = ?
                   WHERE article_url = ?""",
                (
                    article.title,
                    article.author,
                    article.publish_time.isoformat() if article.publish_time else None,
                    article.fetched_at.isoformat() if article.fetched_at else None,
                    article.status,
                    article.markdown_path,
                    article.content_hash,
                    article.summary,
                    article.error_message,
                    article.fail_count,
                    article.article_url,
                ),
            )
            conn.commit()
            row = conn.execute(
                "SELECT id FROM articles WHERE article_url = ?",
                (article.article_url,),
            ).fetchone()
            article_id = row["id"]
        finally:
            conn.close()
        return article_id

    def update_status(self, article_id: int, status: str):
        conn = self._get_conn()
        conn.execute(
            "UPDATE articles SET status = ? WHERE id = ?", (status, article_id)
        )
        conn.commit()
        conn.close()

    def increment_fail_count(self, article_id: int):
        conn = self._get_conn()
        conn.execute(
            "UPDATE articles SET fail_count = fail_count + 1 WHERE id = ?",
            (article_id,),
        )
        conn.commit()
        conn.close()

    def check_content_changed(self, article_url: str, new_hash: str) -> bool:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT content_hash FROM articles WHERE article_url = ?",
            (article_url,),
        ).fetchone()
        conn.close()
        if row is None:
            return True
        return row["content_hash"] != new_hash

    def get_articles_by_date(self, target_date: date) -> list[Article]:
        conn = self._get_conn()
        date_str = target_date.isoformat()
        rows = conn.execute(
            """SELECT * FROM articles
               WHERE DATE(fetched_at) = ?
               ORDER BY fetched_at DESC""",
            (date_str,),
        ).fetchall()
        conn.close()
        return [self._row_to_article(row) for row in rows]

    def get_unnotified_articles(self, target_date: date) -> list[Article]:
        conn = self._get_conn()
        date_str = target_date.isoformat()
        rows = conn.execute(
            """SELECT * FROM articles
               WHERE DATE(fetched_at) = ? AND status = 'fetched'
               ORDER BY fetched_at DESC""",
            (date_str,),
        ).fetchall()
        conn.close()
        return [self._row_to_article(row) for row in rows]

    def batch_update_status(self, article_ids: list[int], status: str):
        conn = self._get_conn()
        placeholders = ",".join("?" for _ in article_ids)
        conn.execute(
            f"UPDATE articles SET status = ? WHERE id IN ({placeholders})",
            [status] + article_ids,
        )
        conn.commit()
        conn.close()
