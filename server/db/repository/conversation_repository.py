import uuid

from sqlalchemy import func

from server.db.models.conversation_model import ConversationModel
from server.db.models.message_model import MessageModel
from server.db.session import with_session
from server.memory.token_info_memory import get_token_info


@with_session
def add_conversation_to_db(session, chat_type, name="", conversation_id=None, assistant_id=None):
    """
    新增聊天记录
    """
    if not conversation_id:
        conversation_id = uuid.uuid4().hex
    c = ConversationModel(id=conversation_id, chat_type=chat_type, name=name, assistant_id=assistant_id,
                          create_by=get_token_info().get("userId"))

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
def get_conversation_from_db(session, assistant_id: int = -1, page: int = 1, limit: int = 10):
    userId = get_token_info().get("userId")
    if userId is None or userId == "":
        return [], 0
    page_size = abs(limit)
    page_num = max(page, 1)
    offset = (page_num - 1) * page_size
    filters = [ConversationModel.create_by == str(userId)]
    if assistant_id >= 0:
        filters.append(ConversationModel.assistant_id == assistant_id)
    conversations = (session.query(ConversationModel).filter(*filters)
                     .order_by(ConversationModel.create_time.desc()).offset(offset).limit(page_size).all())
    total = session.query(func.count(ConversationModel.id)).filter(*filters).scalar()
    data = []
    for c in conversations:
        data.append(c.dict())
    return data, total
