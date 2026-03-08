import os
import logging
import psycopg2
from psycopg2 import pool
from contextlib import contextmanager
from config.settings import DATABASE_URL

logger = logging.getLogger(__name__)

class DatabaseClient:
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.connection_pool = None

    def connect(self):
        try:
            # Initialize a connection pool
            self.connection_pool = psycopg2.pool.SimpleConnectionPool(
                1, 20, dsn=self.database_url
            )
            if self.connection_pool:
                logger.info("Successfully connected to PostgreSQL connection pool")
                self.create_tables()
        except (Exception, psycopg2.DatabaseError) as error:
            logger.error(f"Error connecting to PostgreSQL: {error}")

    def disconnect(self):
        if self.connection_pool:
            self.connection_pool.closeall()
            logger.info("PostgreSQL connection pool closed")

    @contextmanager
    def get_cursor(self):
        """Context manager to get a dedicated cursor from the pool."""
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
        logger.info("Ensuring database tables exist...")
        schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
        
        try:
            with open(schema_path, "r") as f:
                schema_sql = f.read()
                
            with self.get_cursor() as cur:
                cur.execute(schema_sql)
            logger.info("Database tables verified.")
        except Exception as e:
            logger.error(f"Error creating tables: {e}")

    def save_chat(self, user_id: str, message: str, response: str):
        try:
            with self.get_cursor() as cur:
                cur.execute(
                    "INSERT INTO chat_history (user_id, message, response) VALUES (%s, %s, %s)",
                    (user_id, message, response)
                )
        except Exception as e:
            logger.error(f"Error saving chat history: {e}")

    def create_job(self, job_name: str, schedule_type: str, schedule_value: str, next_run=None):
        try:
            with self.get_cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO scheduled_jobs (job_name, schedule_type, schedule_value, next_run)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                    """,
                    (job_name, schedule_type, schedule_value, next_run)
                )
                return cur.fetchone()[0]
        except Exception as e:
            logger.error(f"Error creating scheduled job: {e}")
            return None

    def list_jobs(self):
        try:
            with self.get_cursor() as cur:
                cur.execute(
                    "SELECT id, job_name, schedule_type, schedule_value, next_run, created_at FROM scheduled_jobs"
                )
                return cur.fetchall()
        except Exception as e:
            logger.error(f"Error listing scheduled jobs: {e}")
            return []

    def delete_job(self, job_id: int):
        try:
            with self.get_cursor() as cur:
                cur.execute("DELETE FROM scheduled_jobs WHERE id = %s", (job_id,))
                # Return true if any row was deleted
                return cur.rowcount > 0
        except Exception as e:
            logger.error(f"Error deleting scheduled job: {e}")
            return False

# Create a singleton wrapper (or just instantiate dynamically) around the required db connection pattern requested
def connect_db():
    client = DatabaseClient(DATABASE_URL)
    client.connect()
    return client

# Optional global wrapper methods for simplicity if required by users prompt, 
# although OOP approach is typically cleaner in larger projects.
_global_db_client = None

def _get_or_create_client():
    global _global_db_client
    if not _global_db_client:
        _global_db_client = connect_db()
    return _global_db_client

def create_tables():
    _get_or_create_client().create_tables()

def save_chat(user_id, message, response):
    return _get_or_create_client().save_chat(user_id, message, response)

def create_job(job_name, schedule_type, schedule_value, next_run=None):
    return _get_or_create_client().create_job(job_name, schedule_type, schedule_value, next_run)

def list_jobs():
    return _get_or_create_client().list_jobs()

def delete_job(job_id):
    return _get_or_create_client().delete_job(job_id)
