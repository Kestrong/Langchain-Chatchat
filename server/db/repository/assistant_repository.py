import uuid

from sqlalchemy import func

from server.db.models.assistant_model import AssistantModel
from server.db.models.knowledge_base_model import KnowledgeBaseModel
from server.db.session import with_session
from server.memory.token_info_memory import get_token_info


@with_session
def add_assistant_to_db(session, name: str, code: str, avatar: str, prompt: str, model_name: str, prologue: str,
                        history_len: int, knowledge_base_ids: str, force_feedback: str, extra: dict, model_config: dict,
                        sort_id: int):
    if not code:
        code = str(uuid.uuid4()).upper()[:8]
    c = AssistantModel(name=name, code=code, avatar=avatar, prompt=prompt, model_name=model_name, prologue=prologue,
                       knowledge_base_ids=knowledge_base_ids, force_feedback=force_feedback, history_len=history_len,
                       create_by=get_token_info().get("userId"), extra=extra,
                       model_config=model_config, sort_id=sort_id)
    session.add(c)
    session.flush()
    return c.id


@with_session
def update_assistant_to_db(session, name: str, code: str, assistant_id: int, avatar: str, prompt: str, model_name: str,
                           history_len: int, prologue: str, knowledge_base_ids: str, force_feedback: str, extra: dict,
                           model_config: dict, sort_id: int):
    assistant: AssistantModel = session.query(AssistantModel).filter(AssistantModel.id == assistant_id).first()
    if assistant is not None:
        assistant.name = name
        if code and assistant.code != code:
            assistant.code = code
        if not assistant.code:
            assistant.code = str(uuid.uuid4()).upper()[:8]
        assistant.avatar = avatar
        assistant.prompt = prompt
        assistant.model_name = model_name
        assistant.prologue = prologue
        assistant.knowledge_base_ids = knowledge_base_ids
        assistant.force_feedback = force_feedback
        assistant.history_len = history_len
        assistant.extra = extra if extra is not None else assistant.extra
        assistant.model_config = model_config if model_config is not None else assistant.model_config
        assistant.sort_id = sort_id
    else:
        raise ValueError("Assistant with id {} does not exist".format(assistant))
    return assistant.id


@with_session
def delete_assistant_from_db(session, assistant_id: int):
    session.query(AssistantModel).filter(AssistantModel.id == assistant_id).delete()
    return assistant_id


@with_session
def get_assistant_from_db(session, page: int = 1, size: int = 100, keyword: str = None):
    page_size = abs(size)
    page_num = max(page, 1)
    offset = (page_num - 1) * page_size
    filters = []
    if keyword is not None and keyword.strip() != '':
        filters.append(AssistantModel.name.ilike('%{}%'.format(keyword)))
    assistants = (session.query(AssistantModel).filter(*filters).order_by(AssistantModel.sort_id.asc()).offset(offset)
                  .limit(page_size).all())
    total = session.query(func.count(AssistantModel.id)).filter(*filters).scalar()
    data = []
    for c in assistants:
        data.append(c.dict())
    return data, total


@with_session
def get_assistant_detail_from_db(session, assistant_id: int):
    assistant: AssistantModel = session.query(AssistantModel).filter(AssistantModel.id == assistant_id).first()
    if assistant is None:
        return None
    data = assistant.dict()
    if assistant.knowledge_base_ids is not None and assistant.knowledge_base_ids != '':
        kb_ids = []
        for k in assistant.knowledge_base_ids.split(","):
            if k.isdigit():
                kb_ids.append(int(k))
        kbs = session.query(KnowledgeBaseModel).filter(KnowledgeBaseModel.id.in_(kb_ids)).all()
        data['knowledge_bases'] = [k.dict() for k in kbs]
    else:
        data['knowledge_bases'] = []
    return data


@with_session
def get_assistant_simple_from_db(session, assistant_id: int) -> dict:
    assistant: AssistantModel = session.query(AssistantModel).filter(AssistantModel.id == assistant_id).first()
    if assistant is None:
        return {}
    data = assistant.dict()
    return data
