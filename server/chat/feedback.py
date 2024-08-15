from typing import Any, Dict

import requests
from fastapi import Body

from configs import logger, log_verbose, LLM_MODELS
from server.db.repository import feedback_message_to_db, get_message_by_id
from server.memory.token_info_memory import get_token_info
from server.model_workers.base import ApiChatQimingParams
from server.utils import BaseResponse


def post_feedback_to_qiming(model_name: str, score: int, reason: str, extra: dict):
    if model_name == 'qiming-api':
        params = ApiChatQimingParams(messages=[]).load_config(worker_name=model_name)
        headers = {"X-APP-ID": params.api_key, "X-APP-KEY": params.secret_key}
        extra['feedbackProvice'] = params.role_meta['prov']
        feedbackProvider = get_token_info().get('staffName')
        if feedbackProvider is None or feedbackProvider.strip() == '':
            feedbackProvider = params.role_meta.get('feedbackProvider', '灵晞平台')
        extra['feedbackProvider'] = feedbackProvider
        extra['likes'] = str(score)
        extra['feedback'] = reason if reason is not None and reason != '' else '回答很准确'
        with requests.post(url=params.feedbackUrl, json=extra, headers=headers, timeout=10) as response:
            if response.status_code != 200:
                response.raise_for_status()
            json_data = response.json()
            if str(json_data.get('code')) != "0":
                logger.error(json_data)
                raise Exception('调用启明赞踩接口失败！')


def post_feedback_to_iotqwen(message_id: str, model_name: str, score: int):
    if model_name == 'iotqwen-api':
        params = ApiChatQimingParams(messages=[]).load_config(worker_name=model_name)
        headers = {"Authorization": f"Bearer {params.api_key}",
                   "Content-Type": "application/json"}
        data = {
            "rating": 'likes' if score >= 0 else 'dislikes',
            "user": params.role_meta.get('user')
        }
        message = get_message_by_id(message_id=message_id)
        third_message_id = None
        if message:
            third_message_id = message.get('meta_data', {}).get("third_message_id")
        if not third_message_id:
            logger.error('没有关联第三方消息id，无法点赞')
            return None
        with requests.post(url=params.feedbackUrl.format(message_id=third_message_id), json=data, headers=headers,
                           timeout=10) as response:
            if response.status_code != 200:
                response.raise_for_status()
            json_data = response.json()
            if str(json_data.get('result')) != "success":
                logger.error(json_data)
                raise Exception('调用物联网大模型赞踩接口失败！')


def chat_feedback(message_id: str = Body(..., max_length=32, description="聊天记录id"),
                  model_name: str = Body(LLM_MODELS[0], description="LLM 模型名称。"),
                  extra: Dict[str, Any] = Body({}, description="额外的属性"),
                  score: int = Body(0, max=100, description="用户评分，满分100，越大表示评价越高"),
                  reason: str = Body("", description="用户评分理由，比如不符合事实等")
                  ):
    try:
        post_feedback_to_qiming(model_name, score, reason, extra)
        post_feedback_to_iotqwen(message_id, model_name, score)
        feedback_message_to_db(message_id, score, reason)
    except Exception as e:
        msg = f"反馈聊天记录出错： {e}"
        logger.error(f'{e.__class__.__name__}: {msg}',
                     exc_info=e if log_verbose else None)
        return BaseResponse(code=500, msg=msg)

    return BaseResponse(code=200, msg=f"已反馈聊天记录 {message_id}")
