from dddesign.structure.applications import Application, ApplicationFactory

from app.probe_context.infrastructure.repositories.probe import ProbeRepository, probe_repository_impl


class ProbeApp(Application):
    repo: ProbeRepository = probe_repository_impl

    async def liveness(self):
        pass

    async def readiness(self):
        await self.repo.get_pg_version()
        await self.repo.get_ch_version()

    async def sentry_debug(self):
        division_by_zero = 1 / 0
        return division_by_zero


probe_app_factory = ApplicationFactory[ProbeApp](application_class=ProbeApp)
