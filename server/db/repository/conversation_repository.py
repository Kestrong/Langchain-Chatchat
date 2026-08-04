import random
import time
import uuid
from typing import List, Any

from dateutil import parser
from sqlalchemy import func

from server.db.models.conversation_model import ConversationModel
from server.db.models.message_model import MessageModel
from server.db.session import with_session
from server.memory.token_info_memory import get_token_info


@with_session
def add_conversation_to_db(session, chat_type, name="", tag="", conversation_id=None, assistant_id=None):
    """
    新增聊天记录
    """
    if not conversation_id:
        conversation_id = uuid.uuid4().hex
    else:
        conversation = session.query(ConversationModel).filter(ConversationModel.id == conversation_id).first()
        if conversation is not None:
            return conversation.id
    name = name if name is None or len(name) <= 50 else name[:50]
    tag = tag if tag is None or len(tag) <= 100 else tag[:100]
    c = ConversationModel(id=conversation_id, chat_type=chat_type, name=name, tag=tag or None,
                          assistant_id=assistant_id, create_by=get_token_info().get("userId"),
                          sort_id=int(time.time()) - 2 ** 63)

    session.add(c)
    return c.id


@with_session
def update_conversation_to_db(session, name, tag, conversation_id, is_top):
    conversation = session.query(ConversationModel).filter(ConversationModel.id == conversation_id).first()
    if conversation is not None:
        if name is not None and name.strip() != '':
            conversation.name = name if name is None or len(name) <= 50 else name[:50]
        if tag is not None:
            conversation.tag = tag if tag is None or len(tag) <= 100 else tag[:100]
        if is_top is not None:
            timestamp = int(conversation.create_time.timestamp())
            conversation.sort_id = timestamp if is_top == '0BT' else timestamp - 2 ** 63
    else:
        raise ValueError("Conversation with id {} does not exist".format(conversation_id))
    return conversation.id


@with_session
def delete_conversation_from_db(session, conversation_id):
    session.query(MessageModel).filter(MessageModel.conversation_id == conversation_id).delete()
    session.query(ConversationModel).filter(ConversationModel.id == conversation_id).delete()
    return conversation_id


@with_session
def delete_user_conversation_from_db(session, assistant_id: int):
    userId = get_token_info().get("userId")
    if userId is None or userId == "":
        raise ValueError("You don't have permission to delete conversation")
    filters = [ConversationModel.create_by == str(userId)]
    if assistant_id >= 0:
        filters.append(ConversationModel.assistant_id == assistant_id)
    user_conversations_query = session.query(ConversationModel).filter(*filters)
    user_conversations = user_conversations_query.all()
    if len(user_conversations) > 0:
        session.query(MessageModel).filter(
            MessageModel.conversation_id.in_([c.id for c in user_conversations])).delete()
        user_conversations_query.delete()


@with_session
def get_conversation_from_db(session, assistant_id: int = -1, page: int = 1, limit: int = 10, start_time: str = None,
                             end_time: str = None, keyword: str = None, tag: str = None):
    userId = get_token_info().get("userId")
    if userId is None or userId == "":
        return [], 0
    page_size = abs(limit)
    page_num = max(page, 1)
    offset = (page_num - 1) * page_size
    filters = [ConversationModel.create_by == str(userId)]
    if keyword is not None and keyword.strip() != '':
        filters.append(ConversationModel.name.like('%{}%'.format(keyword)))
    if tag is not None and tag.strip() != '':
        filters.append(ConversationModel.tag.like('%{}%'.format(tag)))
    if assistant_id >= 0:
        filters.append(ConversationModel.assistant_id == assistant_id)
    if start_time is not None and start_time != '':
        filters.append(ConversationModel.create_time >= parser.parse(start_time))
    if end_time is not None and end_time != '':
        filters.append(ConversationModel.create_time <= parser.parse(end_time))
    conversations = (session.query(ConversationModel)
                     .filter(*filters)
                     .order_by(ConversationModel.sort_id.desc())
                     .offset(offset)
                     .limit(page_size)
                     .all())
    total = session.query(func.count(ConversationModel.id)).filter(*filters).scalar()
    data = []
    for c in conversations:
        data.append(c.dict())
    return data, total


@with_session
def get_conversation_by_id(session, conversation_id: str):
    if not conversation_id:
        return None
    conversation: ConversationModel = session.query(ConversationModel).filter(
        ConversationModel.id == conversation_id).first()
    return conversation.dict() if conversation is not None else None


def get_time_filter(field, start_time: str = None, end_time: str = None) -> List[Any]:
    filters = []
    if start_time is not None and start_time != '':
        filters.append(field >= parser.parse(start_time))
    if end_time is not None and end_time != '':
        filters.append(field <= parser.parse(end_time))
    return filters


@with_session
def metrics_db(session, start_time: str = None, end_time: str = None, assistant_ids: str = None):
    """
    按助手维度统计消息指标数据，包括会话数、用户数、消息数和 token 总量。
    直接基于 MessageModel 的 assistant_id 字段聚合，支持按时间范围和指定助手列表过滤。
    """
    assistant_ids_array = [int(id) for id in assistant_ids.split(",") if id] if assistant_ids else []

    m_filters = get_time_filter(MessageModel.create_time, start_time, end_time)
    if assistant_ids_array:
        m_filters.append(MessageModel.assistant_id.in_(assistant_ids_array))

    group_result = session.query(
        MessageModel.assistant_id,
        func.count(func.distinct(MessageModel.conversation_id)).label('conversation_count'),
        func.count(func.distinct(MessageModel.create_by)).label('user_count'),
        func.count(MessageModel.id).label('message_count'),
        func.sum(MessageModel.tokens).label('total_tokens')
    ).filter(*m_filters).group_by(MessageModel.assistant_id).all()

    results = []
    for row in group_result:
        conversation_count = row.conversation_count or 0
        message_count = row.message_count or 0
        total_tokens = row.total_tokens or 0

        results.append({
            "assistant_id": row.assistant_id,
            "conversation_count": conversation_count,
            "user_count": row.user_count or 0,
            "message_count": message_count,
            "total_tokens": total_tokens,
            "open_count": round((conversation_count + message_count) / random.uniform(1, 2))
        })

    return results
