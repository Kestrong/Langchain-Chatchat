from typing import Any, Dict

from fastapi import Body

from configs import logger, log_verbose, LLM_MODELS
from server.db.repository import feedback_message_to_db, get_message_by_id, get_conversation_by_id, \
    get_assistant_simple_from_db
from server.memory.message_i18n import Message_I18N
from server.model_workers.base import ApiChatWithFeedbackParams
from server.utils import BaseResponse, get_httpx_client


def post_feedback_to_dify(message_id: str, model_name: str, score: int, reason: str):
    params = ApiChatWithFeedbackParams(messages=[]).load_config(worker_name=model_name)
    if 'DifyWorker' == params.provider:
        feedback_url = params.feedbackUrl
        api_key = None
        data = {
            "rating": 'like' if score >= 0 else 'dislike',
            "user": params.role_meta.get('user'),
            "content": reason
        }
        message = get_message_by_id(message_id=message_id)
        third_message_id = None
        if message:
            meta_data = message.get('meta_data', {})
            third_message_id = meta_data.get("third_message_id")
            if 'user' in meta_data:
                data['user'] = meta_data.get('user')
            if 'api_key' in meta_data:
                api_key = meta_data.get('api_key')
        if not third_message_id:
            logger.error('没有关联第三方消息id，无法点赞')
            return None
        extra_headers = params.role_meta.get("extra_headers") or {}
        conv = get_conversation_by_id(conversation_id=message.get('conversation_id'))
        if conv:
            assistant = get_assistant_simple_from_db(assistant_id=conv.get('assistant_id'))
            if assistant:
                model_config = assistant.get('model_config', {})
                if not api_key:
                    api_key = model_config.get("api_key")
                feedback_url = model_config.get("feedbackUrl") or feedback_url
                extra_headers.update(model_config.get("extra_headers") or {})
        if not feedback_url:
            logger.error('没有配置feedback_url，无法点赞')
            return None
        if not api_key:
            api_key = params.api_key
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", **extra_headers}
        with get_httpx_client(timeout=5) as client:
            response = client.post(url=feedback_url.format(message_id=third_message_id), json=data,
                                   headers=headers)
            if response.status_code != 200:
                logger.error(response.text)
                response.raise_for_status()
            json_data = response.json()
            if str(json_data.get('result')) != "success":
                logger.error(json_data)
                raise Exception('调用dify赞踩接口失败！')


def post_feedback_to_fastgpt(message_id: str, model_name: str, score: int, reason: str):
    params = ApiChatWithFeedbackParams(messages=[]).load_config(worker_name=model_name)
    if 'FastgptWorker' == params.provider:
        feedback_url = params.feedbackUrl
        api_key = params.api_key
        appId = None
        data = {
            "chatId": "chatId",
            "dataId": message_id,
            "userGoodFeedback": reason
        }
        message = get_message_by_id(message_id=message_id)
        if message:
            data['chatId'] = message.get('conversation_id')
            meta_data = message.get('meta_data', {})
            if 'appId' in meta_data:
                appId = meta_data.get('appId')
        conv = get_conversation_by_id(conversation_id=message.get('conversation_id'))
        extra_headers = params.role_meta.get("extra_headers") or {}
        if conv:
            assistant = get_assistant_simple_from_db(assistant_id=conv.get('assistant_id'))
            if assistant:
                model_config = assistant.get('model_config', {})
                api_key = model_config.get("api_key") or api_key
                if not appId:
                    appId = model_config.get('appId')
                extra_headers.update(model_config.get("extra_headers") or {})
                feedback_url = model_config.get("feedbackUrl") or feedback_url
        if not feedback_url:
            logger.error('没有配置feedback_url，无法点赞')
            return None
        if not appId:
            appId = params.role_meta.get('appId')
        data['appId'] = appId
        headers = {"Authorization": api_key, "Content-Type": "application/json", **extra_headers}
        with get_httpx_client(timeout=5) as client:
            response = client.post(url=feedback_url, json=data, headers=headers)
            if response.status_code != 200:
                logger.error(response.text)
                response.raise_for_status()
            json_data = response.json()
            if str(json_data.get('code')) != "200":
                logger.error(json_data)
                raise Exception('调用fastgpt赞踩接口失败！')


def chat_feedback(message_id: str = Body(..., max_length=64, description="聊天记录id"),
                  model_name: str = Body(LLM_MODELS[0], description="LLM 模型名称。"),
                  extra: Dict[str, Any] = Body({}, description="额外的属性"),
                  score: int = Body(0, max=100, description="用户评分，满分100，越大表示评价越高"),
                  reason: str = Body("", description="用户评分理由，比如不符合事实等")
                  ):
    try:
        post_feedback_to_dify(message_id, model_name, score, reason)
        post_feedback_to_fastgpt(message_id, model_name, score, reason)
        feedback_message_to_db(message_id, score, reason)
    except Exception as e:
        msg = f"反馈聊天记录出错： {e}"
        logger.error(f'{e.__class__.__name__}: {msg}', exc_info=e if log_verbose else None)
        return BaseResponse(code=500, msg=Message_I18N.API_FEEDBACK_ERROR.value)

    return BaseResponse(code=200, msg=Message_I18N.API_FEEDBACK_SUCCESS.value)
