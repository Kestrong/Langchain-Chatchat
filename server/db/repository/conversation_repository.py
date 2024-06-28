import uuid

from server.db.models.conversation_model import ConversationModel
from server.db.models.message_model import MessageModel
from server.db.session import with_session
from server.memory.token_info_memory import get_token_info


@with_session
def add_conversation_to_db(session, chat_type, name="", conversation_id=None):
    """
    新增聊天记录
    """
    if not conversation_id:
        conversation_id = uuid.uuid4().hex
    c = ConversationModel(id=conversation_id, chat_type=chat_type, name=name, create_by=get_token_info().get("userId"))

    session.add(c)
    return c.id


@with_session
def update_conversation_to_db(session, name, conversation_id):
    conversation = session.query(ConversationModel).filter(ConversationModel.id == conversation_id).first()
    if conversation is not None:
        conversation.name = name
    else:
        raise ValueError("Conversation with id {} does not exist".format(conversation_id))
    return conversation.id


@with_session
def delete_conversation_from_db(session, conversation_id):
    session.query(MessageModel).filter(MessageModel.conversation_id == conversation_id).delete()
    session.query(ConversationModel).filter(ConversationModel.id == conversation_id).delete()
    return conversation_id


@with_session
def get_conversation_from_db(session, user_id, limit: int = 10):
    conversations = session.query(ConversationModel).filter(ConversationModel.create_by == user_id).order_by(ConversationModel.create_time.desc()).limit(limit).all()
    data = []
    for c in conversations:
        data.append(c.dict())
    return data
