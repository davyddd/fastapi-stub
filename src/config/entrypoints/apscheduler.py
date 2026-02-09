from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from config.entrypoints.dramatiq import dramatiq_facade_impl
from config.logging.sentry import configure_sentry

scheduler = BlockingScheduler()

dramatiq_facade_impl.setup_tasks()
for job_path, crontab, job_name in dramatiq_facade_impl.get_cron_jobs():
    scheduler.add_job(job_path, trigger=CronTrigger.from_crontab(crontab), name=job_name)

configure_sentry()
