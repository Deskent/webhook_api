import os

import pytest
from dotenv import load_dotenv
try:
    load_dotenv()
except:
    pass


PROXY_USER: str = os.getenv('PROXY_USER')
PROXY_PASSWORD: str = os.getenv('PROXY_PASSWORD')
DEFAULT_PROXY: str = os.getenv('DEFAULT_PROXY')
BASE_API_URL: str = os.getenv('BASE_API_URL')
PROXY_TEST_URL: str = os.getenv('PROXY_TEST_URL')
ADMINS: list = os.getenv('ADMINS')[1:-1].replace('"', '').split(',')
USERNAME: str = os.getenv('TEST_USERNAME')
REPONAME: str = os.getenv('TEST_REPONAME')


@pytest.fixture
def username() -> str:
    return USERNAME


@pytest.fixture
def repo_name() -> str:
    return REPONAME


@pytest.fixture
def payload(username, repo_name) -> dict:
    return dict(
        stage='dev',
        branch='test',
        ssh_url=f'git@github.com:{username}/{repo_name}.git',
        repository_name=repo_name,
        version='test-1.0',
        build='test-1.0',
        user=username,
        path=f'/home/{username}/deploy'
    )
