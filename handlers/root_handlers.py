import hashlib
import hmac
import json

from fastapi import APIRouter, Request, Header, Response, status, Depends

from config import logger, settings
from services.deploy import deploy_or_copy, update_repository


root_router = APIRouter()


def validate_signature(header, body):
    sha_name, github_signature = header.split('=')
    secret_signature = hmac.new(
        key=settings.GITHUB_SECRET.encode("utf-8"),
        msg=body,
        digestmod=hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(secret_signature, github_signature)


async def check_hook(
        request: Request,
        x_hub_signature_256: str = Header(None),
        user_agent: str = Header(None),
        x_github_event: str = Header(None),
        content_length: int = Header(...)
):
    if x_github_event not in ('push', 'workflow_run', 'workflow_job'):
        logger.error(f"Wrong event: {x_github_event}")
        return {"result": "Event wrong"}
    if content_length > 1_000_000:
        logger.error(f"Content too long: {content_length}")
        return {"result": "Content too long"}
    if not user_agent.startswith('GitHub-Hookshot/'):
        logger.error(f"User agent FAIL: {user_agent}")
        return {"result": "User agent fail"}
    if not validate_signature(header=x_hub_signature_256, body=await request.body()):
        logger.error(f"Wrong content: {x_hub_signature_256}")
        return {"result": "Wrong content"}


@root_router.get('/', tags=['root'])
def root():
    return {"root": "OKidoki"}


@root_router.post('/', status_code=status.HTTP_200_OK, tags=['deploy'])
async def deploy(
        request: Request,
        hook_is_not_valid: dict = Depends(check_hook)
):
    answer: dict = {"result": "ok"}
    if hook_is_not_valid:
        logger.warning(hook_is_not_valid)
        return answer

    try:
        data: dict = await request.json()
        data_str = '\n\n'.join(f"{k}: {v}" for k, v in data.items())
        logger.debug(f"Data: \n{data_str}")
        if data['repository']['name'] in settings.UPDATE:
            update_repository(data)
        else:
            deploy_or_copy(data)
    except json.decoder.JSONDecodeError as err:
        logger.error(err)
    return answer
