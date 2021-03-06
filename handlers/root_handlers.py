import hmac
import hashlib
import json

from fastapi import APIRouter, Request, Header, Response, status

from config import logger, settings
from services.deploy import deploy_or_copy, action_report


root_router = APIRouter()


def validate_signature(header, body):
    sha_name, github_signature = header.split('=')
    secret_signature = hmac.new(
        key=settings.GITHUB_SECRET.encode("utf-8"),
        msg=body,
        digestmod=hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(secret_signature, github_signature)


@root_router.get('/', tags=['root'])
def root():
    return {"root": "OKidoki"}


@root_router.post('/', status_code=status.HTTP_200_OK, tags=['deploy'])
async def deploy(
        request: Request,
        response: Response,
        x_hub_signature_256: str = Header(None),
        user_agent: str = Header(None),
        x_github_event: str = Header(None),
        content_length: int = Header(...)
):
    if x_github_event not in ('push', 'workflow_run'):
        logger.error(f"Wrong event: {x_github_event}")
        response.status_code = 400
        return {"result": "Event wrong"}
    if content_length > 1_000_000:
        logger.error(f"Content too long: {content_length}")
        response.status_code = 400
        return {"result": "Content too long"}
    if not user_agent.startswith('GitHub-Hookshot/'):
        logger.error(f"User agent FAIL: {user_agent}")
        response.status_code = 400
        return {"result": "User agent fail"}
    if not validate_signature(header=x_hub_signature_256, body=await request.body()):
        logger.error(f"Wrong content: {x_hub_signature_256}")
        response.status_code = 400
        return {"result": "Wrong content"}
    try:
        data: dict = await request.json()
        logger.info(f'Data: {data}')
        if data.get('action') == 'completed':
            action_report(data)
        else:
            deploy_or_copy(data)
    except json.decoder.JSONDecodeError as err:
        logger.error(err)
        return {"result": "json error"}
    return {"result": "ok"}
