import datetime
import os
import uuid
from typing import Dict

from dateutil import parser
from sqlalchemy import func, String, cast

from server.db.models.assistant_model import AssistantModel
from server.db.models.conversation_model import ConversationModel
from server.db.models.message_model import MessageModel
from server.db.repository import add_conversation_to_db
from server.db.session import with_session
from server.memory.token_info_memory import get_token_info


@with_session
def add_message_to_db(session, conversation_id: str, chat_type, query, response=None, message_id=None,
                      assistant_id=None, tag: str = None, metadata: Dict = {}, store: bool = True):
    """
    新增聊天记录
    """
    if not message_id:
        message_id = uuid.uuid4().hex
    if not store:
        return message_id
    conversation_id = add_conversation_to_db(chat_type=chat_type, conversation_id=conversation_id, name=query,
                                             tag=tag, assistant_id=assistant_id)
    m = MessageModel(id=message_id, chat_type=chat_type, query=query, response=response,
                     conversation_id=conversation_id, create_by=get_token_info().get("userId"),
                     tokens=len(response) if response else 0, meta_data=metadata)
    session.add(m)
    session.commit()
    return m.id


@with_session
def update_message(session, message_id, response: str = None, metadata: Dict = None, append: bool = False,
                   response_time: datetime.datetime = None):
    """
    更新已有的聊天记录
    """
    m = session.query(MessageModel).filter_by(id=message_id).first()
    if m is not None:
        if m.response_time is None and response_time is not None:
            m.response_time = response_time
        if response is not None:
            if m.response and append:
                m.response += response
            else:
                m.response = response
            m.tokens = len(m.response) + (len(m.query) if m.query else 0)
        if isinstance(metadata, dict):
            if m.meta_data is None:
                m.meta_data = metadata
            else:
                metadata.update(m.meta_data)
                m.meta_data = metadata
        return message_id


@with_session
def get_message_by_id(session, message_id) -> dict:
    """
    查询聊天记录
    """
    m = session.query(MessageModel).filter_by(id=message_id).first()
    if m is not None:
        return m.dict()
    return {}


@with_session
def feedback_message_to_db(session, message_id, feedback_score, feedback_reason):
    """
    反馈聊天记录
    """
    m = session.query(MessageModel).filter_by(id=message_id).first()
    if m is not None:
        m.feedback_score = feedback_score
        m.feedback_reason = feedback_reason
        m.feedback_time = datetime.datetime.now()
        session.commit()
        return m.id


@with_session
def filter_message(session, conversation_id: str, limit: int = 10, not_response: bool = True, reverse: bool = False,
                   meta_data_key_exists: list = None):
    # 用户最新的query 也会插入到db，忽略这个message record
    filters = [MessageModel.conversation_id == conversation_id]
    if not_response:
        filters.append(MessageModel.response.isnot(None))
    if meta_data_key_exists:
        for key in meta_data_key_exists:
            filters.append(cast(MessageModel.meta_data, String).contains(key))
    messages = session.query(MessageModel).filter(*filters).order_by(
        MessageModel.create_time.asc() if reverse else MessageModel.create_time.desc()).limit(limit).all()
    # 直接返回 List[MessageModel] 报错
    data = []
    for m in messages:
        data.append(m.dict())
    return data


@with_session
def filter_message_page(session, conversation_id: str, page: int = 1, limit: int = 10):
    page_size = abs(limit)
    page_num = max(page, 1)
    offset = (page_num - 1) * page_size
    # 用户最新的query 也会插入到db，忽略这个message record
    filters = [MessageModel.conversation_id == conversation_id, MessageModel.response.isnot(None)]
    messages = session.query(MessageModel).filter(*filters).order_by(MessageModel.create_time.desc()).offset(
        offset).limit(limit).all()
    total = session.query(func.count(MessageModel.id)).filter(*filters).scalar()
    # 直接返回 List[MessageModel] 报错
    data = []
    for m in messages:
        is_response = m.response is not None and m.response.strip() != ''
        expired = datetime.datetime.now() - m.create_time >= datetime.timedelta(minutes=30)
        if m.response_time is None and (is_response or expired):
            m.response_time = m.create_time + datetime.timedelta(seconds=3)
        data.append(m.dict())
    return data, total


@with_session
def delete_message_from_db(session, message_id):
    session.query(MessageModel).filter(MessageModel.id == message_id).delete()
    return message_id


@with_session
def list_user_feedback_messages(session, query_keyword: str = None, response_keyword: str = None,
                                assistant_name_keyword: str = None, start_time: str = None, end_time: str = None,
                                page: int = 1, limit: int = 10, count: bool = True):
    query = session.query(
        MessageModel.id,
        MessageModel.query,
        MessageModel.response,
        MessageModel.feedback_time,
        MessageModel.feedback_score,
        MessageModel.feedback_reason,
        AssistantModel.name,
        AssistantModel.name_en
    ).join(
        ConversationModel, ConversationModel.id == MessageModel.conversation_id
    ).join(
        AssistantModel, AssistantModel.id == ConversationModel.assistant_id
    )

    query = query.filter(MessageModel.feedback_score.isnot(None))

    if query_keyword:
        query = query.filter(MessageModel.query.like(f"%{query_keyword}%"))

    if response_keyword:
        query = query.filter(MessageModel.response.like(f"%{response_keyword}%"))

    if assistant_name_keyword:
        query = query.filter(
            (AssistantModel.name.like(f"%{assistant_name_keyword}%")) |
            (AssistantModel.name_en.like(f"%{assistant_name_keyword}%"))
        )

    if start_time:
        query = query.filter(MessageModel.feedback_time >= parser.parse(start_time))

    if end_time:
        query = query.filter(MessageModel.feedback_time <= parser.parse(end_time))

    # 分页处理
    page_size = abs(limit)
    page_num = max(page, 1)
    offset = (page_num - 1) * page_size

    # 执行查询
    messages = query.order_by(MessageModel.feedback_time.desc()).offset(offset).limit(page_size).all()
    total = query.count() if count else None

    # 转换结果为字典列表
    data = []
    for m in messages:
        data.append({
            "id": m.id,
            "query": m.query,
            "response": m.response,
            "feedback_time": m.feedback_time,
            "feedback_score": m.feedback_score,
            "feedback_reason": m.feedback_reason,
            "assistant_name": m.name,
            "assistant_name_en": m.name_en
        })

    return data, total


@with_session
def get_query_by_assistant_id(session, assistant_id: int = None, limit: int = 100, is_self: bool = False):
    message_query = session.query(MessageModel.id, MessageModel.query)

    filters = [MessageModel.query.isnot(None),
               MessageModel.create_time >= datetime.datetime.now() - datetime.timedelta(
                   days=int(os.environ.get("HOT_QUERY_DAYS", 365)))]
    if is_self is True:
        filters.append(MessageModel.create_by == get_token_info().get("userId"))
    if assistant_id and assistant_id > 0:
        filters.append(ConversationModel.assistant_id == assistant_id)
        message_query.join(
            ConversationModel, ConversationModel.id == MessageModel.conversation_id
        )

    recent_messages = message_query.filter(*filters).order_by(MessageModel.create_time.desc()).limit(limit).all()

    return [(m.id, m.query) for m in recent_messages]
