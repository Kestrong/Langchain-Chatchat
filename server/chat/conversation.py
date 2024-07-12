from fastapi import Body, Query

from configs.basic_config import logger, log_verbose
from server.db.repository.conversation_repository import add_conversation_to_db, update_conversation_to_db, \
    delete_conversation_from_db, get_conversation_from_db
from server.db.repository.message_repository import filter_message as filter_message_db, delete_message_from_db
from server.utils import BaseResponse


def create_conversation(
        chat_type: str = Body(description="会话类型，可选值：llm_chat，knowledge_base_chat，search_engine_chat，agent_chat"),
        name: str = Body(description="会话名称")) -> BaseResponse:
    try:
        conversation_id = add_conversation_to_db(chat_type=chat_type, name=name)
    except Exception as e:
        msg = f"创建会话出错： {e}"
        logger.error(f'{e.__class__.__name__}: {msg}',
                     exc_info=e if log_verbose else None)
        return BaseResponse(code=500, msg=msg)
    return BaseResponse(code=200, data={'conversation_id': conversation_id})


def update_conversation(id: str = Body(description="会话id"),
                        name: str = Body(description="会话名称")) -> BaseResponse:
    try:
        conversation_id = update_conversation_to_db(conversation_id=id, name=name)
    except Exception as e:
        msg = f"修改会话出错： {e}"
        logger.error(f'{e.__class__.__name__}: {msg}',
                     exc_info=e if log_verbose else None)
        return BaseResponse(code=500, msg=msg)
    return BaseResponse(code=200, data={'conversation_id': conversation_id})


def delete_conversation(id: str = Query(description="会话id")) -> BaseResponse:
    try:
        conversation_id = delete_conversation_from_db(conversation_id=id)
    except Exception as e:
        msg = f"删除会话出错： {e}"
        logger.error(f'{e.__class__.__name__}: {msg}',
                     exc_info=e if log_verbose else None)
        return BaseResponse(code=500, msg=msg)
    return BaseResponse(code=200, data={'conversation_id': conversation_id})


def filter_message(id: str = Query(description="会话id"),
                   limit: int = Query(default=10, description='消息数量')) -> BaseResponse:
    messages = filter_message_db(conversation_id=id, limit=limit)
    return BaseResponse(code=200, data={'messages': messages})


def filter_conversation(user_id: str = Query(description="用户id"),
                        limit: int = Query(default=10, description='会话数量')) -> BaseResponse:
    conversations = get_conversation_from_db(user_id=user_id, limit=limit)
    return BaseResponse(code=200, data={'conversations': conversations})

def delete_message(message_id: str = Query(description="消息id")) -> BaseResponse:
    try:
        message_id = delete_message_from_db(message_id=message_id)
    except Exception as e:
        msg = f"删除消息出错： {e}"
        logger.error(f'{e.__class__.__name__}: {msg}',
                     exc_info=e if log_verbose else None)
        return BaseResponse(code=500, msg=msg)
    return BaseResponse(code=200, data={'message_id': message_id})