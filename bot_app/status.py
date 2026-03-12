import psutil


def get_system_status():
    cpu = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory().percent
    disk = psutil.disk_usage("/").percent

    result = f"""
SYSTEM STATUS

CPU Usage:  {cpu} %
RAM Usage:  {ram} %
Disk Usage: {disk} %
"""

    return result