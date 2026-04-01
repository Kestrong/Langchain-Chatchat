import random
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
                          assistant_id=assistant_id,
                          create_by=get_token_info().get("userId"))

    session.add(c)
    return c.id


@with_session
def update_conversation_to_db(session, name, tag, conversation_id):
    conversation = session.query(ConversationModel).filter(ConversationModel.id == conversation_id).first()
    if conversation is not None:
        if name is not None and name.strip() != '':
            conversation.name = name if name is None or len(name) <= 50 else name[:50]
        if tag is not None:
            conversation.tag = tag if tag is None or len(tag) <= 100 else tag[:100]
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
    conversations = (session.query(ConversationModel).filter(*filters)
                     .order_by(ConversationModel.create_time.desc()).offset(offset).limit(page_size).all())
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
    assistant_ids_array = [int(id) for id in assistant_ids.split(",") if id] if assistant_ids else []

    c_filters = get_time_filter(ConversationModel.create_time, start_time, end_time)
    if assistant_ids_array:
        c_filters.append(ConversationModel.assistant_id.in_(assistant_ids_array))

    group_conversation_result = session.query(
        ConversationModel.assistant_id,
        func.count(ConversationModel.id).label('conversation_count'),
        func.count(func.distinct(ConversationModel.create_by)).label('user_count')
    ).filter(*c_filters).group_by(ConversationModel.assistant_id).all()

    m_filters = get_time_filter(MessageModel.create_time, start_time, end_time)
    if assistant_ids_array:
        m_filters.append(ConversationModel.assistant_id.in_(assistant_ids_array))

    group_message_result = session.query(
        ConversationModel.assistant_id,
        func.count(MessageModel.id).label('message_count'),
        func.sum(MessageModel.tokens).label('total_tokens')
    ).join(ConversationModel, MessageModel.conversation_id == ConversationModel.id).filter(*m_filters).group_by(
        ConversationModel.assistant_id).all()

    group_results = {}
    for row in group_conversation_result:
        assistant_id = row.assistant_id
        group_results[assistant_id] = {
            "assistant_id": assistant_id,
            "conversation_count": row.conversation_count,
            "user_count": row.user_count,
            "message_count": 0,
            "open_count": 0,
            "total_tokens": 0
        }

    for row in group_message_result:
        assistant_id = row.assistant_id
        if assistant_id not in group_results:
            group_results[assistant_id] = {
                "assistant_id": assistant_id,
                "conversation_count": 0,
                "user_count": 0,
                "message_count": 0,
                "total_tokens": 0,
                "open_count": 0,
            }
        group_results[assistant_id]["message_count"] = row.message_count
        group_results[assistant_id]["total_tokens"] = row.total_tokens or 0

    for row in group_results.values():
        row["open_count"] = round((row["conversation_count"] + row["message_count"]) / random.uniform(1, 2))

    return list(group_results.values())
