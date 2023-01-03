import json
import os
import re
import subprocess
from secrets import token_urlsafe
from typing import Tuple

from pydantic import BaseModel

from services.utils import send_message_to_admins
from config import logger, settings, BASE_DIR
from services.exceptions import (
    WrongVersionException, WrongBuildException, ContainerBuildError, ContainerTestError,
    ContainerRunError, ContainerPrepareError, MigrationsError
)

class CommandExecutor(BaseModel):
    path: str = None

    def run_command(self, command: str, path: str = None) -> int:
        if not path:
            path = self.path
        result: 'subprocess.CompletedProcess' = subprocess.run(
            [command],
            shell=True,
            stderr=open(f'{path}/subprocess.log', 'a', encoding='utf-8')
        )
        if result.returncode:
            logger.error(result)
        else:
            logger.debug(result)

        return result.returncode


class GitPull(CommandExecutor):
    branch: str
    repository_name: str
    user: str
    report: str = ''
    full_path: str = ''

    def clone_repository(self) -> None:
        if self.run_command(
                f'git clone -b {self.branch} git@github.com:{self.user}/{self.repository_name}.git {self.full_path}'
        ):
            text = "\nОшибка клонирования"
            self.report += text
            raise ContainerBuildError(detail=text)

        self.report += '\nКлонирование: ОК'

    def pull_repository(self) -> None:
        if self.run_command(
                f'cd {self.full_path} '
                f'&& git checkout {self.branch}'
                f'&& git pull'
        ):
            text = f"\nОшибка пулла"
            self.report += text
            raise ContainerBuildError(detail=text)
        self.report += '\nПулл: ОК'


class Payload(GitPull):
    stage: str
    version: str
    build: str
    ssh_url: str
    container: str = ''
    do_migration: bool = False


class Docker(Payload):

    def deploy(self) -> bool:
        try:
            if not self._prepare():
                return False
            self._build_container()
            if self.do_migration:
                self._run_migrations()
            self._testing_container()
            self._running_container()
            self.run_command(f'docker rmi $(docker images -q)')
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

    def _copy_env(self) -> None:
        if self.run_command(
            f'cp {self.path}/.env {self.full_path}'
        ):
            text = "\nОшибка копирования .env файла"
            self.report += text
            raise ContainerBuildError(detail=text)
        self.report += '\nКопирование: ОК'

    def _build_container(self) -> int:
        logger.info(f"Start building container: {self.container}")
        if not os.path.exists(self.full_path):
            self.clone_repository()
        self._copy_env()
        self.pull_repository()
        docker_file_path = self.full_path
        if not os.path.exists(docker_file_path):
            docker_file_path = self.path
        status = -1
        for _ in range(2):
            status: int = self.run_command(
                f'cd {docker_file_path} '
                f'&& git checkout {self.branch}'
                f'&& VERSION="{self.stage}-{self.version}" APPNAME="{self.repository_name.lower()}" docker-compose build'
            )
            if not status:
                break
        if status == 0:
            self.report += f"\nСборка: ОК"
            return status

        text = "\nОшибка сборки"
        self.report += text
        logger.debug(f"Docker data: \n{self.dict()}")
        raise ContainerBuildError(detail=text)

    def _run_migrations(self) -> int:
        logger.info(f"Start migrations container: {self.container}")
        status = self.run_command(
            f'cd {self.full_path} '
            f'&& git checkout {self.branch}'
            f'&& VERSION="{self.stage}-{self.version}" APPNAME="{self.repository_name.lower()}" docker-compose run --rm app alembic upgrade head'
        )
        if status == 0:
            self.report += "\nМиграции: ОК"
            return status

        text = "\nОшибка миграций"
        self.report += text
        raise MigrationsError(detail=text)

    def _testing_container(self):
        logger.info(f"Start testing container: {self.container}")
        status = self.run_command(
            f'cd {self.full_path} '
            f'&& git checkout {self.branch}'
            f'&& VERSION="{self.stage}-{self.version}" APPNAME="{self.repository_name.lower()}" docker-compose run --rm app pytest -k server tests/'
        )
        if status == 0:
            self.report += "\nТесты: ОК"
            return status

        text = "\nОшибка тестирования"
        self.report += text
        raise ContainerTestError(detail=text)

    def _running_container(self):
        logger.info(f"Starting container: {self.container}")
        status: int = self.run_command(
            f'cd {self.full_path}'
            f'&& docker-compose down --remove-orphans'
            f'&& VERSION="{self.stage}-{self.version}" APPNAME="{self.repository_name.lower()}" docker-compose up -d'
            f'&& echo --- Done'
        )
        if status == 0:
            self.report += f"\nРазвертывание: ОК"
            return status
        text = "\nОшибка развертывания"
        self.report += text
        raise ContainerRunError(detail=text)


def get_action_payload(data: dict) -> dict:
    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    if data.get('action') != 'completed':
        logger.info(f'Action: {data.get("action")}')
        return {}

    workflow_job: dict = data.get("workflow_job", {})

    if workflow_job.get('conclusion') != 'success':
        logger.info(f'Conclusion: {workflow_job.get("conclusion")}')
        return {}
    branch: str = is_branch_valid(data, workflow_job.get('head_branch'))
    if not branch:
        logger.info(f'Wrong branch: {workflow_job.get("head_branch")}')
        return {}

    stage: str = settings.STAGES[branch]

    repository_name: str = data.get("repository", {}).get("name")
    user: str = data.get("repository", {}).get("owner", {}).get("login").lower()
    ssh_url: str = data.get("repository", {}).get("ssh_url")

    message: str = data.get("head_commit", {}).get("message", '')
    do_migration: bool = '__do_migration__' in message
    version = build = workflow_job.get('head_sha')
    if message:
        version, build = _get_version_and_build(message)

    action_report(data)

    return dict(
        stage=stage,
        branch=branch,
        ssh_url=ssh_url,
        repository_name=repository_name,
        version=version,
        build=build,
        user=user,
        do_migration=do_migration
    )


def get_not_action_payload(data: dict) -> dict:
    branch: str = is_branch_valid(data)
    if not branch:
        return {}
    stage: str = settings.STAGES[branch]
    ssh_url: str = data.get("repository", {}).get("ssh_url", '')
    repository_name: str = data.get("repository", {}).get("name")
    message: str = data.get("head_commit", {}).get("message", '')
    do_migration: bool = '__do_migration__' in message
    version, build = _get_version_and_build(message)
    user: str = data.get("repository", {}).get("owner", {}).get("name").lower()
    return dict(
        stage=stage,
        branch=branch,
        ssh_url=ssh_url,
        repository_name=repository_name,
        version=version,
        build=build,
        user=user,
        do_migration=do_migration
    )


def deploy_or_copy(data: dict) -> None:
    if data.get('action'):
        payload = get_action_payload(data)
        logger.info(f'\n\nPayload with action: {payload} \n\n')
    else:
        payload = get_not_action_payload(data)
    if not payload:
        return

    logger.info(f"Result: {payload}")
    if payload['repository_name'].endswith('_client'):
        return _create_clients_archive_files(payload=Docker(**payload))
    Docker(**payload).deploy()


def action_report(data: dict) -> None:
    workflow_job: dict = data.get('workflow_job')
    repository_name: str = data.get("repository", {}).get("name")
    result: str = workflow_job.get("conclusion")
    branch: str = workflow_job.get('head_branch')
    head_sha: str = workflow_job.get('head_sha')
    text = (
        f"\nAction result: {result}"
        f"\nRepository: {repository_name}"
        f"\nBranch: {branch}"
        f"\nSHA: {head_sha}"
    )
    send_message_to_admins(text)


def is_branch_valid(data: dict, branch: str = '') -> str:
    if not branch:
        branch: str = data.get("ref", '').split('/')[-1]
    if branch not in settings.STAGES.keys():
        logger.warning(f'Wrong branch: {branch}')
        return ''
    return branch


def update_repository(data: dict) -> None:
    branch: str = is_branch_valid(data)
    if not branch:
        return
    repository = data['repository']
    git_pull = GitPull(
        path=str(BASE_DIR),
        branch=branch,
        repository_name=repository['name'],
        user=repository['owner']['name'],
        full_path=str(BASE_DIR),
        report=f"Git pull for {repository['name']}"
    )
    git_pull.pull_repository()


def _get_version_and_build(message: str) -> Tuple[str, ...]:
    version: list = re.findall(r"version:(.{,20})]", message)
    if not version:
        text = f"Version not found in message: {message}"
        logger.error(text)
        send_message_to_admins(text)
        raise WrongVersionException
    build: list = re.findall(r'build:(.{,20})]', message)
    if not build:
        text = f"Build not found in message: {message}"
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
