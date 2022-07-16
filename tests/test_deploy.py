import pytest
from services.deploy import Docker, ContainerBuildError, ContainerPrepareError


def test_prepare_error_wrong_repository(payload):
    payload.update(repository_name='error')
    obj = Docker(**payload)
    assert obj._prepare() is False


def test_prepare_error_wrong_path(payload):
    payload.update(path='error')
    obj = Docker(**payload)
    with pytest.raises(ContainerPrepareError):
        obj._prepare()


def test_build_wrong_branch(payload):
    payload.update(branch='error')
    obj = Docker(**payload)
    obj._prepare()
    with pytest.raises(ContainerBuildError):
        obj._build_container()


@pytest.mark.full
def test_build_container_ok(payload):
    obj = Docker(**payload)
    obj._prepare()
    assert obj._build_container() == 0


@pytest.mark.full
def test_testing_container_ok(payload):
    obj = Docker(**payload)
    obj._prepare()
    obj._build_container()
    assert obj._testing_container() == 0


@pytest.mark.full
def test_docker_deploy_ok(payload):
    assert Docker(**payload).deploy() is True
