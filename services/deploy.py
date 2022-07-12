import os
import re
from secrets import token_urlsafe
from typing import Tuple

from pydantic import BaseModel

from services.utils import send_message_to_admins
from config import logger, settings
from services.exceptions import WrongVersionException, WrongBuildException


class Payload(BaseModel):
    branch: str
    stage: str
    repository_name: str
    version: str
    build: str
    user: str
    ssh_url: str
    path: str = ''
    container: str = ''

    def docker_deploy(self) -> None:
        if self.repository_name not in settings.APPLICATIONS:
            logger.warning(f'Wrong application: {self.repository_name}')
            return
        self.path = f'/home/{self.user}/deploy/{self.repository_name}/{self.stage}'
        self.container = f'{self.repository_name}-{self.stage}-{self.version}'
        os.system(f'docker rmi $(docker images -q)')
        if self._build_container():
            return
        if self._testing_container():
            return
        self._docker_deploy()

    def _docker_deploy(self):
        logger.info(f"Starting container: {self.container}")
        status: int = os.system(
            f'cd {self.path} &&'
            f'docker-compose -f docker-compose-{self.repository_name}-{self.stage}.yml down &&'
            f'export VERSION="{self.stage}-{self.version}" &&'
            f'docker-compose -f docker-compose-{self.repository_name}-{self.stage}.yml up -d &&'
            f'echo --- Done'
        )

        text = f"Контейнер {self.container} развернут.\nBuild: {self.build}"
        if status:
            text = (
                f"Ошибка развертывания {self.container}."
                f"\nСтатус-код: {status}"
                f"\nBuild: {self.build}"
            )
        send_message_to_admins(text)

    def _testing_container(self):
        status: int = os.system(
            f'cd {self.path}/{self.repository_name} &&'
            'docker run python:3.10-alpine pip install pytest && python -s -v -m pytest --disable-warnings tests/ &&'
            f'echo --- Delete temporary {self.path} &&'
            f'cd {self.path} &&'
            f'rm -rf {self.repository_name} &&'
            f'echo --- Done'
        )
        text = f"Контейнер {self.container} протестирован.\nBuild: {self.build}"
        if status:
            text = (
                f"Ошибка тестирования контейнера {self.container}."
                f"\nСтатус-код: {status}"
                f"\nBuild: {self.build}"
            )
        send_message_to_admins(text)

        return status

    def _build_container(self) -> int:
        logger.info(f"Start building container: {self.container}")
        status: int = os.system(
            f'echo --- Go to {self.path} &&'
            f'cd {self.path} &&'
            f'echo --- Cloning {self.ssh_url} branch {self.branch} to {self.path} &&'
            f'git clone {self.ssh_url} &&'
            f'echo --- Go to {self.repository_name} &&'
            f'cd {self.repository_name} &&'
            f'echo --- Checkout to branch {self.branch} &&'
            f'git checkout {self.branch} &&'
            f'echo --- Docker build start &&'
            f'docker build . -t {self.repository_name}:{self.stage}-{self.version} &&'
            f'echo --- Done'
        )
        text = f"Контейнер {self.container} собран.\nBuild: {self.build}"
        if status:
            text = (
                f"Ошибка сборки контейнера {self.container}."
                f"\nСтатус-код: {status}"
                f"\nBuild: {self.build}"
            )
        send_message_to_admins(text)

        return status


def deploy_or_copy(data: dict):
    logger.info(f'Data: {data}')
    branch: str = data.get("ref", '').split('/')[-1]
    if branch != settings.STAGE:
        logger.warning(f'Wrong branch: {branch}')
        return
    stage: str = settings.STAGES[branch]
    ssh_url: str = data.get("repository", {}).get("ssh_url", '')
    repository_name: str = data.get("repository", {}).get("name")
    message: str = data.get("head_commit", {}).get("message", '')
    version, build = _get_version_and_build(message)
    user: str = data.get("repository", {}).get("owner", {}).get("name").lower()
    result = Payload(**dict(
        stage=stage,
        branch=branch,
        ssh_url=ssh_url,
        repository_name=repository_name,
        version=version,
        build=build,
        user=user
    ))
    logger.info(f"Result: {result}")
    if repository_name.endswith('_client'):
        _create_clients_archive_files(result)
    else:
        result.docker_deploy()


def _get_version_and_build(message: str) -> Tuple[str, ...]:
    version: list = re.findall(r"version:(.{,20})]", message)
    if not version:
        text = f"Wrong version: {message}"
        logger.error(text)
        send_message_to_admins(text)
        raise WrongVersionException
    build: list = re.findall(r'build:(.{,20})]', message)
    if not build:
        text = f"Wrong build: {message}"
        logger.error(text)
        send_message_to_admins(text)
        raise WrongBuildException
    return version[0], build[0]


def _create_clients_archive_files(payload: Payload) -> None:
    if payload.repository_name not in settings.CLIENTS:
        logger.warning(f'Wrong application: {payload.repository_name}')
        return
    path = '/home/deskent/deploy/clients'
    temp_dir = token_urlsafe(20)
    logger.info(f"Copy files for {payload.repository_name}-{payload.stage}-{payload.build}")
    rep_path = os.path.join(path, payload.repository_name)
    temp_path = os.path.join(path, temp_dir)
    status: int = os.system(
        f'echo --- Creating {rep_path} &&'
        f'mkdir -p {rep_path} &&'
        f'echo --- Creating {temp_path} &&'
        f'mkdir {temp_path} &&'
        f'echo --- Go to {temp_path} &&'
        f'cd {temp_path} &&'
        f'echo --- Cloning {payload.ssh_url} branch {payload.branch} to {temp_path} &&'
        f'git clone {payload.ssh_url} &&'
        f'echo --- Go to {payload.repository_name} &&'
        f'cd {payload.repository_name} &&'
        f'echo --- Checkout to branch {payload.branch} &&'
        f'git checkout {payload.branch} &&'
        f'echo --- Copy files &&'
        f'cp {temp_path}/{payload.repository_name}/archive/*.* {rep_path} &&'
        f'cp {temp_path}/{payload.repository_name}/README.md {rep_path} &&'
        f'echo --- Delete temporary {temp_path} &&'
        f'cd {path} &&'
        f'rm -rf {temp_dir} &&'
        f'echo --- Done'
    )
    text = f"Файлы {payload.repository_name}-{payload.stage}-{payload.build} скопированы"
    if status:
        text = (
            f"Ошибка копирования {payload.repository_name}-{payload.stage}-{payload.build}."
            f"\nСтатус-код: {status}"
            f"\nBuild: {payload.build}"
        )
    send_message_to_admins(text)

