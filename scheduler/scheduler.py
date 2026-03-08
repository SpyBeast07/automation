import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from config.settings import DATABASE_URL

logger = logging.getLogger(__name__)

class JobScheduler:
    def __init__(self):
        # Configure job stores with fallback
        try:
            from apscheduler.jobstores.memory import MemoryJobStore
            jobstores = {
                'default': SQLAlchemyJobStore(url=DATABASE_URL)
            }
            # Test connection if possible or just rely on APScheduler's behavior
            self.scheduler = AsyncIOScheduler(jobstores=jobstores)
            logger.info("Initialized persistent scheduler with PostgreSQL store.")
        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL job store: {e}. Falling back to MemoryJobStore.")
            jobstores = {
                'default': MemoryJobStore()
            }
            self.scheduler = AsyncIOScheduler(jobstores=jobstores)

    def start(self):
        """Starts the scheduler."""
        if not self.scheduler.running:
            logger.info("Starting scheduler...")
            try:
                self.scheduler.start()
            except Exception as e:
                logger.error(f"Error starting scheduler with current stores: {e}. Attempting memory fallback.")
                from apscheduler.jobstores.memory import MemoryJobStore
                self.scheduler = AsyncIOScheduler(jobstores={'default': MemoryJobStore()})
                self.scheduler.start()
        else:
            logger.warning("Scheduler is already running.")

    def stop(self):
        """Stops the scheduler."""
        if self.scheduler.running:
            logger.info("Stopping persistent scheduler...")
            self.scheduler.shutdown()
        else:
            logger.warning("Scheduler is not running.")

    def schedule_interval(self, func, seconds, job_id=None, **kwargs):
        """Schedules a job to run at fixed intervals."""
        logger.info(f"Scheduling interval job: {func.__name__} every {seconds}s")
        return self.scheduler.add_job(
            func, 
            'interval', 
            seconds=seconds, 
            id=job_id, 
            replace_existing=True,
            **kwargs
        )

    def schedule_cron(self, func, cron_expression, job_id=None, **kwargs):
        """
        Schedules a job using a cron expression.
        Expression format: minute hour day month day_of_week
        """
        logger.info(f"Scheduling cron job: {func.__name__} with '{cron_expression}'")
        # Split cron expression into components
        parts = cron_expression.split()
        if len(parts) != 5:
            raise ValueError("Cron expression must have 5 parts: 'min hour day month dow'")
            
        return self.scheduler.add_job(
            func,
            'cron',
            minute=parts[0],
            hour=parts[1],
            day=parts[2],
            month=parts[3],
            day_of_week=parts[4],
            id=job_id,
            replace_existing=True,
            **kwargs
        )

    def schedule_once(self, func, run_at: datetime, job_id=None, **kwargs):
        """Schedules a job to run once at a specific time."""
        logger.info(f"Scheduling one-time job: {func.__name__} at {run_at}")
        return self.scheduler.add_job(
            func,
            'date',
            run_date=run_at,
            id=job_id,
            replace_existing=True,
            **kwargs
        )

    def delete_job(self, job_id):
        """Removes a job by its ID."""
        logger.info(f"Removing job: {job_id}")
        try:
            self.scheduler.remove_job(job_id)
            return True
        except Exception as e:
            logger.error(f"Error removing job {job_id}: {e}")
            return False

    def list_jobs(self):
        """Lists all currently scheduled jobs."""
        return self.scheduler.get_jobs()

# Helper wrappers as requested
_scheduler_instance = None

def get_scheduler():
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = JobScheduler()
    return _scheduler_instance

def start_scheduler():
    get_scheduler().start()

def schedule_interval(func, seconds, job_id=None, **kwargs):
    return get_scheduler().schedule_interval(func, seconds, job_id, **kwargs)

def schedule_cron(func, cron_expression, job_id=None, **kwargs):
    return get_scheduler().schedule_cron(func, cron_expression, job_id, **kwargs)

def schedule_once(func, run_at, job_id=None, **kwargs):
    return get_scheduler().schedule_once(func, run_at, job_id, **kwargs)

def delete_job(job_id):
    return get_scheduler().delete_job(job_id)

def list_jobs():
    return get_scheduler().list_jobs()
