import os
import re
from secrets import token_urlsafe
from typing import Tuple

from services.utils import send_message_to_admins
from config import logger, settings
from services.exceptions import WrongVersionException, WrongBuildException


def deploy_or_copy(data: dict):
    logger.info(f'Data: {data}')
    stages = {
        "test": "dev",
        "main": "prod"
    }
    branch: str = data.get("ref", '').split('/')[-1]
    if branch != settings.STAGE:
        logger.warning(f'Wrong branch: {branch}')
        return
    stage = stages[branch]
    ssh_url: str = data.get("repository", {}).get("ssh_url", '')
    repository_name: str = data.get("repository", {}).get("name")
    message: str = data.get("head_commit", {}).get("message", '')
    version, build = get_version_and_build(message)
    user = data.get("repository", {}).get("owner", {}).get("name").lower()
    result = dict(
        stage=stage,
        branch=branch,
        ssh_url=ssh_url,
        repository_name=repository_name,
        version=version,
        build=build,
        user=user
    )
    logger.info(f"Result: {result}")
    if repository_name.endswith('_client'):
        create_clients_archive_files(**result)
        return
    elif repository_name.endswith("_api"):
        return
    docker_deploy(**result)


def get_version_and_build(message: str) -> Tuple[str, ...]:
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


def create_clients_archive_files(
        stage: str, ssh_url: str, repository_name: str, build: str, branch: str, *args, **kwargs
) -> None:
    path = '/home/deskent/deploy/clients'
    temp_dir = token_urlsafe(20)
    logger.info(f"Copy files for {repository_name}-{stage}-{build}")
    rep_path = os.path.join(path, repository_name)
    temp_path = os.path.join(path, temp_dir)
    status: int = os.system(
        f'echo Creating {rep_path} &&'
        f'mkdir -p {rep_path} &&'
        f'echo Creating {temp_path} &&'
        f'mkdir {temp_path} &&'
        f'echo Go to {temp_path} &&'
        f'cd {temp_path} &&'
        f'echo Cloning {ssh_url} branch {branch} to {temp_path} &&'
        f'git clone {ssh_url} &&'
        f'echo Go to {repository_name} &&'
        f'cd {repository_name} &&'
        f'echo Checkout to brabch {branch} &&'
        f'git checkout {branch} &&'
        f'echo Copy files &&'
        f'cp {temp_path}/archive/*.* {rep_path} &&'
        f'cp {temp_path}/README.md {rep_path} &&'
        f'echo Delete temporary {temp_path} &&'
        f'cd {path} &&'
        f'rm -rf {temp_dir} &&'
        f'echo Done'
    )
    text = f"Файлы {repository_name}-{stage}-{build} скопированы"
    if status:
        text = f"Ошибка копирования {repository_name}-{stage}-{build}.\nСтатус-код: {status}"
    send_message_to_admins(text)


def docker_deploy(
        stage: str, repository_name: str, build: str, user: str, *args, **kwargs
) -> None:
    path = f'/home/{user}/deploy/{repository_name}/{stage}'
    status: int = os.system(
        f'echo Create {path} &&'
        f'mkdir -p {path} &&'
        f'echo Go to {path} &&'
        f'cd {path} &&'
        f'echo Docker down {repository_name}-{stage} &&'
        f'docker-compose -f docker-compose-{repository_name}-{stage}.yml down &&'
        f'echo Docker remove images &&'
        f'docker rmi {user}/{user}:{repository_name}-{build} -f &&'
        f'echo Docker up {repository_name}-{stage} &&'
        f'docker-compose -f docker-compose-{repository_name}-{stage}.yml up -d --build &&'
        f'echo Done'
    )
    text = f"Контейнер {repository_name}-{stage}-{build} развернут."
    if status:
        text = f"Ошибка развертывания {repository_name}-{stage}-{build}.\nСтатус-код: {status}"
    send_message_to_admins(text)
