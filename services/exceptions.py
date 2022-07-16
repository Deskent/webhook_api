from typing import Any, Optional, Dict

from fastapi import HTTPException
from starlette import status

UnauthorizedError = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail='Access denied'
)

NotFoundError = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail='Error data'
)

WrongVersionException = HTTPException(
    status_code=status.HTTP_406_NOT_ACCEPTABLE,
    detail='Wrong version'
)

WrongBuildException = HTTPException(
    status_code=status.HTTP_406_NOT_ACCEPTABLE,
    detail='Wrong build'
)


class ContainerBuildError(HTTPException):
    def __init__(self, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                 detail='Container building error'):
        super(ContainerBuildError, self).__init__(status_code=status_code, detail=detail)


class ContainerTestError(HTTPException):
    def __init__(self, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                 detail='Container testing error'):
        super(ContainerTestError, self).__init__(status_code=status_code, detail=detail)


class ContainerRunError(HTTPException):
    def __init__(self, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                 detail='Container running error'):
        super(ContainerRunError, self).__init__(status_code=status_code, detail=detail)
