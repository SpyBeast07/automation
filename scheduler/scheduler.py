import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

class JobScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()

    def start(self):
        logger.info("Starting scheduler...")
        self.scheduler.start()

    def stop(self):
        logger.info("Stopping scheduler...")
        self.scheduler.shutdown()

    def add_job(self, func, trigger, **kwargs):
        # TODO: Add job scheduling logic
        self.scheduler.add_job(func, trigger, **kwargs)
        logger.info(f"Added new job: {func.__name__}")
