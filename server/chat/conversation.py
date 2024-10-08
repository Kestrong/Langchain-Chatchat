from fastapi import Body, Query

from configs.basic_config import logger, log_verbose
from server.db.repository.conversation_repository import add_conversation_to_db, update_conversation_to_db, \
    delete_conversation_from_db, get_conversation_from_db, delete_user_conversation_from_db
from server.db.repository.message_repository import delete_message_from_db, \
    filter_message_page
from server.memory.message_i18n import Message_I18N
from server.utils import BaseResponse


def create_conversation(chat_type: str = Body(
    description="会话类型，可选值：llm_chat，knowledge_base_chat，search_engine_chat，agent_chat"),
        assistant_id: int = Body(description="助手ID"),
        name: str = Body(description="会话名称")) -> BaseResponse:
    try:
        conversation_id = add_conversation_to_db(chat_type=chat_type, name=name, assistant_id=assistant_id)
    except Exception as e:
        msg = f"创建会话出错： {e}"
        logger.error(f'{e.__class__.__name__}: {msg}',
                     exc_info=e if log_verbose else None)
        return BaseResponse(code=500, msg=Message_I18N.API_CREATE_ERROR.value)
    return BaseResponse(code=200, data={'conversation_id': conversation_id})


def update_conversation(id: str = Body(description="会话id"),
                        name: str = Body(description="会话名称")) -> BaseResponse:
    try:
        conversation_id = update_conversation_to_db(conversation_id=id, name=name)
    except Exception as e:
        msg = f"修改会话出错： {e}"
        logger.error(f'{e.__class__.__name__}: {msg}',
                     exc_info=e if log_verbose else None)
        return BaseResponse(code=500, msg=Message_I18N.API_UPDATE_ERROR.value)
    return BaseResponse(code=200, data={'conversation_id': conversation_id})


def delete_conversation(id: str = Query(description="会话id")) -> BaseResponse:
    try:
        conversation_id = delete_conversation_from_db(conversation_id=id)
    except Exception as e:
        msg = f"删除会话出错： {e}"
        logger.error(f'{e.__class__.__name__}: {msg}',
                     exc_info=e if log_verbose else None)
        return BaseResponse(code=500, msg=Message_I18N.API_DELETE_ERROR.value)
    return BaseResponse(code=200, data={'conversation_id': conversation_id})


def delete_user_conversation(assistant_id: int = Query(-1, description="助手ID")) -> BaseResponse:
    try:
        delete_user_conversation_from_db(assistant_id=assistant_id)
    except Exception as e:
        msg = f"删除用户会话出错： {e}"
        logger.error(f'{e.__class__.__name__}: {msg}',
                     exc_info=e if log_verbose else None)
        return BaseResponse(code=500, msg=Message_I18N.API_DELETE_ERROR.value)
    return BaseResponse(code=200, data={})


def filter_message(id: str = Query(description="会话id"),
                   page: int = Query(default=1, description="页码"),
                   limit: int = Query(default=10, description='消息数量')) -> BaseResponse:
    messages, total = filter_message_page(conversation_id=id, page=page, limit=min(abs(limit), 1000))
    for m in messages:
        metadata = m.get('meta_data')
        if metadata:
            if 'user' in metadata:
                del metadata['user']
            if 'api_key' in metadata:
                del metadata['api_key']
            m['meta_data'] = metadata
    return BaseResponse(code=200, data={'messages': messages, 'total': total})


def filter_conversation(assistant_id: int = Query(-1, description="助手ID"),
                        page: int = Query(default=1, description="页码"),
                        limit: int = Query(default=10, description='会话数量'),
                        keyword: str = Query(default=None, description="关键字搜索")) -> BaseResponse:
    conversations, total = get_conversation_from_db(assistant_id=assistant_id, page=page, limit=min(abs(limit), 1000),
                                                    keyword=keyword)
    return BaseResponse(code=200, data={'conversations': conversations, 'total': total})


def delete_message(message_id: str = Query(description="消息id")) -> BaseResponse:
    try:
        message_id = delete_message_from_db(message_id=message_id)
    except Exception as e:
        msg = f"删除消息出错： {e}"
        logger.error(f'{e.__class__.__name__}: {msg}',
                     exc_info=e if log_verbose else None)
        return BaseResponse(code=500, msg=Message_I18N.API_DELETE_ERROR.value)
    return BaseResponse(code=200, data={'message_id': message_id})
