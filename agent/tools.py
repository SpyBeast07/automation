import logging
import datetime
import asyncio
import sys
from typing import Type, Optional
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
from scheduler.scheduler import schedule_interval, schedule_cron, delete_job, list_jobs

logger = logging.getLogger(__name__)

def _get_bot_instance():
    """Robustly retrieve the shared bot instance from sys.modules."""
    # Check the module name used in main.py
    if "local_telegram_bot" in sys.modules:
        return getattr(sys.modules["local_telegram_bot"], "_bot_instance", None)
    # Fallback to telegram.bot
    if "telegram.bot" in sys.modules:
        return getattr(sys.modules["telegram.bot"], "_bot_instance", None)
    return None

async def notify_telegram(chat_id, message):
    """Helper to send telegram messages asynchronously."""
    try:
        bot = _get_bot_instance()
        if bot:
            await bot.send_message(chat_id=chat_id, text=message)
            logger.info(f"Notification sent to {chat_id}")
        else:
            logger.warning(f"Notification failed: No bot instance found in sys.modules. Available: {[m for m in sys.modules if 'bot' in m]}")
    except Exception as e:
        logger.error(f"Error sending telegram notification: {e}")

class GetCurrentTimeTool(BaseTool):
    name: str = "get_current_time"
    description: str = "Returns the current system time. Useful for scheduling. Takes no input."

    def _run(self, query: Optional[str] = None) -> str:
        now = datetime.datetime.now()
        return f"Current system time: {now.strftime('%Y-%m-%d %H:%M:%S')}"

class ScheduleIntervalTool(BaseTool):
    name: str = "schedule_task_interval"
    description: str = (
        "Schedules a task to run at fixed intervals. "
        "Input should be 'task_name, seconds'. Example: 'Drink Water, 3600'"
    )

    def _run(self, args: str, chat_id: Optional[int] = None) -> str:
        logger.info(f"ScheduleIntervalTool._run called with chat_id={chat_id}")
        try:
            parts = [p.strip() for p in args.split(",")]
            if len(parts) < 2:
                return "Error: Please provide 'task_name, seconds'. Example: 'Refill Water, 3600'"
            
            task_name = parts[0]
            seconds = int(parts[1])

            # Use an async function for the job so APScheduler awaits it correctly
            async def job_func():
                logger.info(f"Background Task Triggered: {task_name} (ChatID: {chat_id})")
                if chat_id:
                    await notify_telegram(chat_id, f"🔔 Task Reminder: {task_name}")
                else:
                    logger.warning(f"No chat_id found for task {task_name}, cannot notify.")
                
            job = schedule_interval(job_func, seconds, job_id=task_name)
            logger.info(f"Job scheduled successfully: {job.id}")
            return f"Successfully scheduled task '{task_name}' every {seconds} seconds. I will notify you here."
        except Exception as e:
            return f"Error: {str(e)}. Ensure input is 'name, seconds'."

class ScheduleCronTool(BaseTool):
    name: str = "schedule_task_cron"
    description: str = (
        "Schedules a task using a cron expression. "
        "Input should be 'task_name, cron_expression'. Example: 'Daily Backup, 0 12 * * *'"
    )

    def _run(self, args: str, chat_id: Optional[int] = None) -> str:
        try:
            parts = [p.strip() for p in args.split(",", 1)]
            if len(parts) < 2:
                return "Error: Please provide 'task_name, cron_expression'. Example: 'Meeting, 0 14 * * 1'"
            
            task_name = parts[0]
            cron_expression = parts[1]

            async def job_func():
                logger.info(f"Background task executing: {task_name}")
                if chat_id:
                    await notify_telegram(chat_id, f"🔔 Scheduled Alert: {task_name}")
                
            job = schedule_cron(job_func, cron_expression, job_id=task_name)
            return f"Successfully scheduled task '{task_name}' ({cron_expression}). I will notify you here."
        except Exception as e:
            return f"Error: {str(e)}. Ensure input is 'name, cron_expression'."

class ListJobsTool(BaseTool):
    name: str = "list_active_jobs"
    description: str = "Lists all currently active scheduled jobs. Takes no input."

    def _run(self, query: Optional[str] = None) -> str:
        try:
            jobs = list_jobs()
            if not jobs:
                return "No active scheduled jobs found."
            
            job_list = "\n".join([f"- ID: {j.id}, Next run: {j.next_run_time}" for j in jobs])
            return f"Active scheduled jobs:\n{job_list}"
        except Exception as e:
            return f"Error listing jobs: {str(e)}"

class RemoveJobTool(BaseTool):
    name: str = "remove_scheduled_job"
    description: str = "Removes a scheduled job by its ID. Example input: 'My Task'"

    def _run(self, job_id: str) -> str:
        try:
            success = delete_job(job_id.strip())
            if success:
                return f"Successfully removed job '{job_id}'."
            else:
                return f"Job '{job_id}' not found."
        except Exception as e:
            return f"Error removing job: {str(e)}"

# Instantiate tools for easy import
get_current_time = GetCurrentTimeTool()
schedule_task_interval = ScheduleIntervalTool()
schedule_task_cron = ScheduleCronTool()
list_active_jobs = ListJobsTool()
remove_scheduled_job = RemoveJobTool()
