from typing import Any, Dict

import requests
from fastapi import Body

from configs import logger, log_verbose, LLM_MODELS
from server.db.repository import feedback_message_to_db
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
            feedbackProvider = '灵晞平台'
        extra['feedbackProvider'] = feedbackProvider
        extra['likes'] = str(score)
        extra['feedback'] = reason if reason is not None and reason != '' else '回答很准确'
        response = requests.post(url=params.feedbackUrl, json=extra, headers=headers)
        if response.status_code != 200:
            response.raise_for_status()
        json_data = response.json()
        if str(json_data.get('code')) != "0":
            logger.info(json_data)


def chat_feedback(message_id: str = Body(..., max_length=32, description="聊天记录id"),
                  model_name: str = Body(LLM_MODELS[0], description="LLM 模型名称。"),
                  extra: Dict[str, Any] = Body({}, description="额外的属性"),
                  score: int = Body(0, max=100, description="用户评分，满分100，越大表示评价越高"),
                  reason: str = Body("", description="用户评分理由，比如不符合事实等")
                  ):
    try:
        feedback_message_to_db(message_id, score, reason)
        post_feedback_to_qiming(model_name, score, reason, extra)
    except Exception as e:
        msg = f"反馈聊天记录出错： {e}"
        logger.error(f'{e.__class__.__name__}: {msg}',
                     exc_info=e if log_verbose else None)
        return BaseResponse(code=500, msg=msg)

    return BaseResponse(code=200, msg=f"已反馈聊天记录 {message_id}")
