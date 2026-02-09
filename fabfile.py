from fabric.api import local, settings

from fab_utils import get_file_hash, update_service_env_file

BASE_IMAGE_TAG = f"baseimage:{get_file_hash('Dockerfile-base')}"
BASE_SERVICE_NAME = 'server'


def base():
    update_service_env_file(BASE_IMAGE_TAG)

    with settings(warn_only=True):
        result = local(f"docker inspect -f '{{.Id}}' {BASE_IMAGE_TAG}", capture=True)

    if result.succeeded:
        return

    local(f'docker build --tag {BASE_IMAGE_TAG} --file ./Dockerfile-base .')


def build(service=BASE_SERVICE_NAME):
    base()
    local(f'docker-compose build {service}')


def _run_command_container(service, command):
    base()

    container_id = local(f"docker ps | grep -E '{service}.*{service}' | awk '{{ print $1 }}' | head -n 1", capture=True)
    if container_id:
        local(f'docker exec -it {container_id} bash -c "{command}"')
    else:
        local(f'docker-compose run --rm --service-ports {service} bash -c "{command}"')


def run():
    _run_command_container(BASE_SERVICE_NAME, 'python manage.py runserver')


def worker():
    _run_command_container('worker', 'python manage.py runworker --watch')


def scheduler():
    _run_command_container('scheduler', 'python manage.py runscheduler')


def bash(service=BASE_SERVICE_NAME):
    _run_command_container(service, 'bash')


def shell(service=BASE_SERVICE_NAME):
    _run_command_container(service, 'python manage.py shell')


def makemigrations(service=BASE_SERVICE_NAME, db='postgres'):
    _run_command_container(service, f'python manage.py makemigrations --db {db}')


def migrate(service=BASE_SERVICE_NAME, db='postgres'):
    _run_command_container(service, f'python manage.py migrate --db {db}')


def tests(service=BASE_SERVICE_NAME):
    _run_command_container(service, 'pytest')


def linters(service=BASE_SERVICE_NAME):
    _run_command_container(
        service,
        "(cd .. && ruff . --config ruff.toml --fix && echo 'Ruff check completed'); "
        "(cd .. && ruff format . --config ruff.toml && echo 'Ruff format completed'); "
        "(cd .. && PYTHONPATH=src lint-imports --config lint-imports.toml && echo 'Import linter completed'); "
        "(cd .. && ty check --config-file ty.toml && echo 'Ty completed'); ",
    )


### Helpers for working with docker


def kill():
    local('docker kill $(docker ps -q)')


def remove_none_images():
    local('docker rmi -f $(docker images -f "dangling=true" -q)')


def remove_all_containers():
    local('docker rm -f $(docker ps -aq)')
    local('docker volume rm -f $(docker volume ls -q)')
