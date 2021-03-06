import os
import re
import subprocess
from secrets import token_urlsafe
from typing import Tuple

from pydantic import BaseModel

from services.utils import send_message_to_admins
from config import logger, settings
from services.exceptions import (
    WrongVersionException, WrongBuildException, ContainerBuildError, ContainerTestError,
    ContainerRunError, ContainerPrepareError
)


class Payload(BaseModel):
    branch: str
    stage: str
    repository_name: str
    version: str
    build: str
    user: str
    ssh_url: str
    path: str = ''
    full_path: str = ''
    container: str = ''
    report: str = ''


class Docker(Payload):

    def deploy(self) -> bool:
        try:
            if not self._prepare():
                return False
            self._build_container()
            self._testing_container()
            self._running_container()
            self._run_command(f'docker rmi $(docker images -q)')
            send_message_to_admins(self.report)
        except (
                ContainerBuildError, ContainerTestError, ContainerRunError, ContainerPrepareError
        ) as err:
            text = err.args[0] if err.args else err.detail
            logger.exception(f"{text}: {err}")
            send_message_to_admins(self.report)
            raise
        return True

    def _prepare(self) -> bool:
        if self.repository_name not in settings.APPLICATIONS:
            logger.warning(f'Wrong application: {self.repository_name}')
            return False
        if not self.path:
            self.path = f'/home/{self.user}/deploy/{self.repository_name}/{self.stage}'
        if not os.path.exists(self.path):
            text = f'\n{self.path} does not exists.'
            self.report += text
            raise ContainerPrepareError(detail=text)
        self.full_path = os.path.join(self.path, self.repository_name)
        self.container = f'{self.repository_name}-{self.stage}-{self.version}'
        self.report += (
            f'\nContainer: {self.container}'
            f'\n[build:{self.build}]'
            f'\n[version:{self.version}]'
            f'\n\nPrepare: OK'
        )
        return True

    def _clone_repository(self) -> None:
        if self._run_command(
            f'git clone -b {self.branch} git@github.com:{self.user}/{self.repository_name}.git {self.full_path}'
        ):
            text = "\n???????????? ????????????????????????"
            self.report += text
            raise ContainerBuildError(detail=text)

        self.report += '\n????????????????????????: ????'

    def _pull_repository(self) -> None:
        if self._run_command(
            f'cd {self.full_path}'
            f'&& git checkout {self.branch}'
            f'&& git pull'
        ):
            text = f"\n???????????? ??????????"
            self.report += text
            raise ContainerBuildError(detail=text)
        self.report += '\n????????: ????'

    def _copy_env(self) -> None:
        if self._run_command(
            f'cp {self.path}/.env {self.full_path}'
        ):
            text = "\n???????????? ?????????????????????? .env ??????????"
            self.report += text
            raise ContainerBuildError(detail=text)
        self.report += '\n??????????????????????: ????'

    def _build_container(self) -> int:
        logger.info(f"Start building container: {self.container}")
        if not os.path.exists(self.full_path):
            self._clone_repository()
        self._copy_env()
        self._pull_repository()

        status = -1
        for _ in range(2):
            status: int = self._run_command(
                f'cd {self.full_path}'
                f'&& git checkout {self.branch}'
                f'&& VERSION="{self.stage}-{self.version}" APPNAME="{self.repository_name.lower()}" docker-compose build'
            )
            if not status:
                break
        if status == 0:
            self.report += f"\n????????????: ????"
            return status

        text = "\n???????????? ????????????"
        self.report += text
        raise ContainerBuildError(detail=text)

    def _testing_container(self):
        logger.info(f"Start testing container: {self.container}")
        status = self._run_command(
            f'cd {self.full_path}'
            f'&& git checkout {self.branch}'
            f'&& VERSION="{self.stage}-{self.version}" APPNAME="{self.repository_name.lower()}" docker-compose run --rm app pytest -k server tests/'
        )
        if status == 0:
            self.report += "\n??????????: ????"
            return status

        text = "\n???????????? ????????????????????????"
        self.report += text
        raise ContainerTestError(detail=text)

    def _running_container(self):
        logger.info(f"Starting container: {self.container}")
        status: int = self._run_command(
            f'cd {self.full_path}'
            f'&& docker-compose down --remove-orphans'
            f'&& VERSION="{self.stage}-{self.version}" APPNAME="{self.repository_name.lower()}" docker-compose up -d'
            f'&& echo --- Done'
        )
        if status == 0:
            self.report += f"\n??????????????????????????: ????"
            return status
        text = "\n???????????? ??????????????????????????"
        self.report += text
        raise ContainerRunError(detail=text)

    def _run_command(self, command: str) -> int:
        result: 'subprocess.CompletedProcess' = subprocess.run(
            [command],
            shell=True,
            stderr=open(f'{self.path}/subprocess.log', 'a', encoding='utf-8')
        )
        if result.returncode:
            logger.error(result)
        else:
            logger.debug(result)

        return result.returncode


def action_report(data: dict) -> None:
    repository_name: str = data.get("workflow_run", {}).get("repository", {}).get("name")
    message: str = data.get("workflow_run", {}).get("head_commit", {}).get("message", '')
    version, build = _get_version_and_build(message)
    conclusion: str = data.get("workflow_run", {}).get("conclusion")
    text = (
        f"\nPYPI: {repository_name}"
        f"\n[build:{build}]"
        f"\n[version:{version}]"
        f"\nResult: {conclusion}"
    )
    send_message_to_admins(text)


def deploy_or_copy(data: dict) -> None:
    branch: str = data.get("ref", '').split('/')[-1]
    if branch not in settings.STAGES.keys():
        logger.warning(f'Wrong branch: {branch}')
        return
    stage: str = settings.STAGES[branch]
    ssh_url: str = data.get("repository", {}).get("ssh_url", '')
    repository_name: str = data.get("repository", {}).get("name")
    message: str = data.get("head_commit", {}).get("message", '')
    version, build = _get_version_and_build(message)
    user: str = data.get("repository", {}).get("owner", {}).get("name").lower()
    payload = dict(
        stage=stage,
        branch=branch,
        ssh_url=ssh_url,
        repository_name=repository_name,
        version=version,
        build=build,
        user=user
    )
    logger.info(f"Result: {payload}")
    if repository_name.endswith('_client'):
        return _create_clients_archive_files(payload=Payload(**payload))
    Docker(**payload).deploy()


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
    text = f"?????????? {payload.repository_name}-{payload.stage}-{payload.build} ??????????????????????"
    if status:
        text = (
            f"???????????? ?????????????????????? {payload.repository_name}-{payload.stage}-{payload.build}."
            f"\n????????????-??????: {status}"
            f"\nBuild: {payload.build}"
        )
    send_message_to_admins(text)
