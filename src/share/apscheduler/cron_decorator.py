CRONTAB_ATTRIBUTE = '__crontab__'


def cron(crontab: str):
    """
    @cron('*/1 * * * *')
    @dramatiq.actor
    def some_cron_task():
        ...
    """

    def decorator(func):
        setattr(func, CRONTAB_ATTRIBUTE, crontab)
        return func

    return decorator
