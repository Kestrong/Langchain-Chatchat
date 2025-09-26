from typing import Any, Dict

from fastapi import Body

from configs import logger, log_verbose, LLM_MODELS
from server.db.repository import feedback_message_to_db, get_message_by_id, get_conversation_by_id, \
    get_assistant_simple_from_db
from server.memory.message_i18n import Message_I18N
from server.memory.token_info_memory import get_token_info
from server.model_workers.base import ApiChatWithFeedbackParams
from server.utils import BaseResponse, get_httpx_client


def post_feedback_to_qiming(message_id: str, model_name: str, score: int, reason: str, extra: dict):
    if model_name == 'qiming-api':
        message = get_message_by_id(message_id=message_id)
        if message:
            meta_data = message.get('meta_data', {})
            if 'third_message_id' in meta_data:
                return None
        params = ApiChatWithFeedbackParams(messages=[]).load_config(worker_name=model_name)
        headers = {"X-APP-ID": params.api_key, "X-APP-KEY": params.secret_key}
        extra['feedbackProvice'] = params.role_meta['prov']
        feedbackProvider = get_token_info().get('staffName')
        if feedbackProvider is None or feedbackProvider.strip() == '':
            feedbackProvider = params.role_meta.get('feedbackProvider', '灵晞平台')
        extra['feedbackProvider'] = feedbackProvider
        extra['likes'] = str(score)
        extra['feedback'] = reason if reason is not None and reason != '' else '回答很准确'
        with get_httpx_client(timeout=5) as client:
            response = client.post(url=params.feedbackUrl, json=extra, headers=headers)
            if response.status_code != 200:
                logger.error(response.text)
                response.raise_for_status()
            json_data = response.json()
            if str(json_data.get('code')) != "0":
                logger.error(json_data)
                raise Exception('调用启明赞踩接口失败！')


def post_feedback_to_dify(message_id: str, model_name: str, score: int, reason: str):
    params = ApiChatWithFeedbackParams(messages=[]).load_config(worker_name=model_name)
    if (model_name == 'iotqwen-api' or 'DifyWorker' == params.provider) and params.feedbackUrl:
        api_key = params.api_key
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
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        conv = get_conversation_by_id(conversation_id=message.get('conversation_id'))
        if conv:
            assistant = get_assistant_simple_from_db(assistant_id=conv.get('assistant_id'))
            if assistant:
                extra_headers = assistant.get('model_config', {}).get("extra_headers") or params.role_meta.get(
                    "extra_headers", {})
                headers.update(extra_headers)
        with get_httpx_client(timeout=5) as client:
            response = client.post(url=params.feedbackUrl.format(message_id=third_message_id), json=data,
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
    if 'FastgptWorker' == params.provider and params.feedbackUrl:
        api_key = params.api_key
        data = {
            "appId": "appId",
            "chatId": "chatId",
            "dataId": message_id,
            "userGoodFeedback": reason
        }
        message = get_message_by_id(message_id=message_id)
        if message:
            data['chatId'] = message.get('conversation_id')
            meta_data = message.get('meta_data', {})
            if 'appId' in meta_data:
                data['appId'] = meta_data.get('appId')
        headers = {"Authorization": api_key, "Content-Type": "application/json"}
        conv = get_conversation_by_id(conversation_id=message.get('conversation_id'))
        if conv:
            assistant = get_assistant_simple_from_db(assistant_id=conv.get('assistant_id'))
            if assistant:
                extra_headers = assistant.get('model_config', {}).get("extra_headers") or params.role_meta.get(
                    "extra_headers", {})
                headers.update(extra_headers)
        with get_httpx_client(timeout=5) as client:
            response = client.post(url=params.feedbackUrl, json=data, headers=headers)
            if response.status_code != 200:
                logger.error(response.text)
                response.raise_for_status()
            json_data = response.json()
            if str(json_data.get('code')) != "200":
                logger.error(json_data)
                raise Exception('调用fastgpt赞踩接口失败！')


def chat_feedback(message_id: str = Body(..., max_length=32, description="聊天记录id"),
                  model_name: str = Body(LLM_MODELS[0], description="LLM 模型名称。"),
                  extra: Dict[str, Any] = Body({}, description="额外的属性"),
                  score: int = Body(0, max=100, description="用户评分，满分100，越大表示评价越高"),
                  reason: str = Body("", description="用户评分理由，比如不符合事实等")
                  ):
    try:
        post_feedback_to_qiming(message_id, model_name, score, reason, extra)
        post_feedback_to_dify(message_id, model_name, score, reason)
        post_feedback_to_fastgpt(message_id, model_name, score, reason)
        feedback_message_to_db(message_id, score, reason)
    except Exception as e:
        msg = f"反馈聊天记录出错： {e}"
        logger.error(f'{e.__class__.__name__}: {msg}',
                     exc_info=e if log_verbose else None)
        return BaseResponse(code=500, msg=Message_I18N.API_FEEDBACK_ERROR.value)

    return BaseResponse(code=200, msg=Message_I18N.API_FEEDBACK_SUCCESS.value)
