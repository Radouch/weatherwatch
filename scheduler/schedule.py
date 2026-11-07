import schedule
import time
import logging
from datetime import datetime
from threading import Lock


logger = logging.getLogger(__name__)


class TimeScheduler:
    def __init__(self, times: list[str]):
        self.times = times
        self.lock = Lock()

    def schedule_job(self, job_func):
        for time_str in self.times:
            schedule.every().day.at(time_str).do(self._wrapped_job(job_func))
            logger.info(f"Scheduled daily job at {time_str}")

    def _wrapped_job(self, job_func):
        def wrapper():
            with self.lock:
                logger.info(f"Running scheduled job at {datetime.now()}")
                job_func()

        return wrapper

    def run_pending(self):
        schedule.run_pending()
        time.sleep(1)
