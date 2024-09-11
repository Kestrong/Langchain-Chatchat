import uuid
from typing import Dict

from sqlalchemy import func

from server.db.models.message_model import MessageModel
from server.db.session import with_session
from server.memory.token_info_memory import get_token_info


@with_session
def add_message_to_db(session, conversation_id: str, chat_type, query, response="", message_id=None,
                      metadata: Dict = {}, store: bool = True):
    """
    新增聊天记录
    """
    if not message_id:
        message_id = uuid.uuid4().hex
    if not store:
        return message_id
    m = MessageModel(id=message_id, chat_type=chat_type, query=query, response=response,
                     conversation_id=conversation_id, create_by=get_token_info().get("userId"),
                     meta_data=metadata)
    session.add(m)
    session.commit()
    return m.id


@with_session
def update_message(session, message_id, response: str = None, metadata: Dict = None):
    """
    更新已有的聊天记录
    """
    m = session.query(MessageModel).filter_by(id=message_id).first()
    if m is not None:
        if response is not None:
            m.response = response
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
        session.commit()
        return m.id


@with_session
def filter_message(session, conversation_id: str, limit: int = 10):
    # 用户最新的query 也会插入到db，忽略这个message record
    filters = [MessageModel.conversation_id == conversation_id, MessageModel.response != '']
    messages = session.query(MessageModel).filter(*filters).order_by(MessageModel.create_time.desc()).limit(limit).all()
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
    filters = [MessageModel.conversation_id == conversation_id, MessageModel.response != '']
    messages = session.query(MessageModel).filter(*filters).order_by(MessageModel.create_time.desc()).offset(
        offset).limit(limit).all()
    total = session.query(func.count(MessageModel.id)).filter(*filters).scalar()
    # 直接返回 List[MessageModel] 报错
    data = []
    for m in messages:
        data.append(m.dict())
    return data, total


@with_session
def delete_message_from_db(session, message_id):
    session.query(MessageModel).filter(MessageModel.id == message_id).delete()
    return message_id
