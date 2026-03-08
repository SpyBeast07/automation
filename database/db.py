import os
import logging
import psycopg2
from psycopg2 import pool
import sqlite3
from contextlib import contextmanager
from config.settings import DATABASE_URL

logger = logging.getLogger(__name__)

class DatabaseClient:
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.connection_pool = None
        self.use_sqlite = False
        self.sqlite_path = "automation.db"

    def connect(self):
        try:
            # Try PostgreSQL first
            self.connection_pool = psycopg2.pool.SimpleConnectionPool(
                1, 20, dsn=self.database_url
            )
            logger.info("Successfully connected to PostgreSQL connection pool")
            self.use_sqlite = False
            self.create_tables()
        except Exception as e:
            logger.warning(f"PostgreSQL connection failed: {e}. Falling back to SQLite.")
            self.use_sqlite = True
            self.create_tables()

    def disconnect(self):
        if self.connection_pool:
            self.connection_pool.closeall()
            logger.info("PostgreSQL connection pool closed")

    @contextmanager
    def get_cursor(self):
        """Context manager to get a cursor from either Postgres or SQLite."""
        if self.use_sqlite:
            conn = sqlite3.connect(self.sqlite_path)
            conn.row_factory = sqlite3.Row
            try:
                cur = conn.cursor()
                yield cur
                conn.commit()
            except Exception as e:
                conn.rollback()
                raise e
            finally:
                conn.close()
        else:
            if not self.connection_pool:
                raise Exception("PostgreSQL pool not initialized")
            conn = self.connection_pool.getconn()
            try:
                with conn.cursor() as cur:
                    yield cur
                conn.commit()
            except:
                conn.rollback()
                raise
            finally:
                self.connection_pool.putconn(conn)

    def create_tables(self):
        logger.info(f"Ensuring database tables exist ({'SQLite' if self.use_sqlite else 'PostgreSQL'})...")
        
        # SQL for tables (Generic enough for both)
        tables = [
            """
            CREATE TABLE IF NOT EXISTS chat_history (
                id SERIAL PRIMARY KEY,
                user_id TEXT,
                message TEXT,
                response TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS scheduled_jobs (
                id SERIAL PRIMARY KEY,
                job_name TEXT,
                schedule_type TEXT,
                schedule_value TEXT,
                next_run TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        ]
        
        # SQLite doesn't support SERIAL or specific TIMESTAMP defaults in the same way, 
        # but it accepts standard SQL well enough for these simple tables.
        if self.use_sqlite:
            tables = [t.replace("SERIAL PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT") for t in tables]
            tables = [t.replace("CURRENT_TIMESTAMP", "(datetime('now','localtime'))") for t in tables]

        try:
            with self.get_cursor() as cur:
                for table_sql in tables:
                    cur.execute(table_sql)
            logger.info("Database tables verified.")
        except Exception as e:
            logger.error(f"Error creating tables: {e}")

    def save_chat(self, user_id: str, message: str, response: str):
        try:
            with self.get_cursor() as cur:
                placeholder = "?" if self.use_sqlite else "%s"
                cur.execute(
                    f"INSERT INTO chat_history (user_id, message, response) VALUES ({placeholder}, {placeholder}, {placeholder})",
                    (user_id, message, response)
                )
        except Exception as e:
            logger.error(f"Error saving chat history: {e}")

    def create_job(self, job_name: str, schedule_type: str, schedule_value: str, next_run=None):
        try:
            with self.get_cursor() as cur:
                placeholder = "?" if self.use_sqlite else "%s"
                cur.execute(
                    f"""
                    INSERT INTO scheduled_jobs (job_name, schedule_type, schedule_value, next_run)
                    VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder})
                    """,
                    (job_name, schedule_type, schedule_value, next_run)
                )
                return True
        except Exception as e:
            logger.error(f"Error creating scheduled job record: {e}")
            return False

    def list_jobs(self):
        try:
            with self.get_cursor() as cur:
                cur.execute("SELECT job_name, schedule_type, schedule_value FROM scheduled_jobs")
                return cur.fetchall()
        except Exception as e:
            logger.error(f"Error listing scheduled jobs: {e}")
            return []

# Singleton pattern helper
_global_db_client = None

def connect_db():
    global _global_db_client
    if not _global_db_client:
        _global_db_client = DatabaseClient(DATABASE_URL)
        _global_db_client.connect()
    return _global_db_client

def save_chat(user_id, message, response):
    return connect_db().save_chat(user_id, message, response)

def create_job(job_name, schedule_type, schedule_value, next_run=None):
    return connect_db().create_job(job_name, schedule_type, schedule_value, next_run)

def list_jobs():
    return connect_db().list_jobs()
