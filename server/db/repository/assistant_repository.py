from server.db.models.assistant_model import AssistantModel
from server.db.models.knowledge_base_model import KnowledgeBaseModel
from server.db.session import with_session
from server.memory.token_info_memory import get_token_info


@with_session
def add_assistant_to_db(session, name: str, avatar: str, prompt: str, model_name: str, prologue: str,
                        knowledge_base_ids: str, extra: dict, model_config: dict, sort_id: int):
    c = AssistantModel(name=name, avatar=avatar, prompt=prompt, model_name=model_name, prologue=prologue,
                       knowledge_base_ids=knowledge_base_ids, create_by=get_token_info().get("userId"), extra=extra,
                       model_config=model_config, sort_id=sort_id)
    session.add(c)
    session.flush()
    return c.id


@with_session
def update_assistant_to_db(session, name: str, assistant_id: int, avatar: str, prompt: str, model_name: str,
                           prologue: str, knowledge_base_ids: str, extra: dict, model_config: dict, sort_id: int):
    assistant: AssistantModel = session.query(AssistantModel).filter(AssistantModel.id == assistant_id).first()
    if assistant is not None:
        assistant.name = name
        assistant.avatar = avatar
        assistant.prompt = prompt
        assistant.model_name = model_name
        assistant.prologue = prologue
        assistant.knowledge_base_ids = knowledge_base_ids
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
def get_assistant_from_db(session, page: int = 1, size: int = 10):
    page_size = abs(size)
    page_num = max(page, 1)
    offset = (page_num - 1) * page_size
    assistants = session.query(AssistantModel).order_by(AssistantModel.sort_id.asc()).offset(offset).limit(
        page_size).all()
    data = []
    for c in assistants:
        data.append(c.dict())
    return data


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
