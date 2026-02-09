import sentry_sdk
from sentry_sdk.integrations.dramatiq import DramatiqIntegration

from config.settings import Environment, settings


def configure_sentry():
    if settings.SENTRY_DSN and settings.ENVIRONMENT != Environment.LOCAL:
        sentry_sdk.init(
            dsn=str(settings.SENTRY_DSN),
            enable_tracing=True,
            integrations=[DramatiqIntegration()],
            environment=str(settings.ENVIRONMENT),
        )
