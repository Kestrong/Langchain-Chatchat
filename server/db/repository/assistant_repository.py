import base64
import io

from PIL import Image
from shortuuid import uuid
from sqlalchemy import func, or_

from server.db.client.ciam_client import get_resource_action_codes
from server.db.models.assistant_model import AssistantModel, WorkflowAssistantModel
from server.db.models.knowledge_base_model import KnowledgeBaseModel
from server.db.session import with_session
from server.memory.token_info_memory import get_token_info


def compress_base64_image(base64_string, output_format='PNG', output_quality=85):
    if not base64_string:
        return None
    # 解码Base64字符串为二进制数据
    base64_data = base64.b64decode(base64_string.split(',')[1] if ',' in base64_string else base64_string)

    # 将二进制数据加载为图像对象
    image = Image.open(io.BytesIO(base64_data))
    image = image.resize((24, 24))

    # 创建一个内存中的文件对象用于保存压缩后的图像
    compressed_image_io = io.BytesIO()

    # 压缩图像并保存到内存文件对象中
    image.save(compressed_image_io, format=output_format, quality=output_quality, optimize=True)

    # 获取压缩后的图像的二进制数据
    compressed_image_io.seek(0)
    compressed_image_data = compressed_image_io.read()

    # 将压缩后的图像二进制数据编码为Base64字符串
    compressed_image_b64 = base64.b64encode(compressed_image_data).decode('utf-8')

    return f"data:image/{output_format.lower()};base64,{compressed_image_b64}"


@with_session
def add_assistant_to_db(session, name: str, name_en: str, code: str, avatar: str, prompt: str, model_name: str,
                        prologue: str, history_len: int, top_k: int, score_threshold: float, knowledge_base_ids: str,
                        force_feedback: str, state: str, extra: dict, model_config: dict, tool_config: dict,
                        workflow_config: dict, sort_id: int):
    if not code:
        code = str(uuid())
    c = WorkflowAssistantModel(name=name, name_en=name_en, code=code, avatar=compress_base64_image(avatar),
                               prompt=prompt, model_name=model_name, state=state or "0BT",
                               prologue=prologue, knowledge_base_ids=knowledge_base_ids, force_feedback=force_feedback,
                               history_len=history_len, top_k=top_k, score_threshold=score_threshold,
                               create_by=get_token_info().get("userId"), extra=extra,
                               model_config=model_config, tool_config=tool_config, workflow_config=workflow_config,
                               sort_id=sort_id)
    session.add(c)
    session.flush()
    return c.id


@with_session
def update_assistant_to_db(session, name: str, name_en: str, code: str, assistant_id: int, avatar: str, prompt: str,
                           model_name: str, history_len: int, top_k: int, score_threshold: float, prologue: str,
                           knowledge_base_ids: str, force_feedback: str, state: str, extra: dict, model_config: dict,
                           tool_config: dict, workflow_config: dict, sort_id: int):
    assistant: WorkflowAssistantModel = session.query(WorkflowAssistantModel).filter(
        WorkflowAssistantModel.id == assistant_id).first()
    if assistant is not None:
        assistant.name = name
        assistant.name_en = name_en
        if state:
            assistant.state = state
        if code and assistant.code != code:
            assistant.code = code
        if not assistant.code:
            assistant.code = str(uuid())
        assistant.avatar = avatar if avatar == assistant.avatar else compress_base64_image(avatar)
        assistant.prompt = prompt
        assistant.model_name = model_name
        assistant.prologue = prologue
        assistant.knowledge_base_ids = knowledge_base_ids
        assistant.force_feedback = force_feedback
        assistant.history_len = history_len
        assistant.top_k = top_k
        assistant.score_threshold = score_threshold
        assistant.extra = extra if extra else assistant.extra
        assistant.model_config = model_config if model_config else assistant.model_config
        assistant.tool_config = tool_config if tool_config else assistant.tool_config
        assistant.workflow_config = workflow_config if workflow_config else assistant.workflow_config
        assistant.sort_id = sort_id
    else:
        raise ValueError("Assistant with id {} does not exist".format(assistant_id))
    return assistant.id


@with_session
def delete_assistant_from_db(session, assistant_id: int):
    session.query(AssistantModel).filter(AssistantModel.id == assistant_id).delete()
    return assistant_id


@with_session
def get_assistants_from_db(session, page: int = 1, size: int = 100, keyword: str = None, code: str = None,
                           states: list = None):
    page_size = abs(size)
    page_num = max(page, 1)
    offset = (page_num - 1) * page_size
    if not states:
        states = ["0BT"]
    filters = [AssistantModel.state.in_(states)]
    if keyword is not None and keyword.strip() != '':
        filters.append(or_(AssistantModel.name.ilike('%{}%'.format(keyword)),
                           AssistantModel.name_en.ilike('%{}%'.format(keyword))))
    if code is not None and code.strip() != '':
        filters.append(AssistantModel.code == code)
    action_codes = get_resource_action_codes()
    if action_codes:
        filters.append(AssistantModel.code.in_(action_codes))
    assistants = (session.query(AssistantModel).filter(*filters).order_by(AssistantModel.sort_id.asc()).offset(offset)
                  .limit(page_size).all())
    total = session.query(func.count(AssistantModel.id)).filter(*filters).scalar()
    data = []
    for c in assistants:
        data.append(c.dict())
    return data, total


@with_session
def get_assistant_detail_from_db(session, assistant_id: int):
    filters = [WorkflowAssistantModel.id == assistant_id]
    assistant: WorkflowAssistantModel = session.query(WorkflowAssistantModel).filter(*filters).first()
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
    filters = [WorkflowAssistantModel.id == assistant_id]
    assistant: WorkflowAssistantModel = session.query(WorkflowAssistantModel).filter(*filters).first()
    if assistant is None:
        return {}
    data = assistant.dict()
    return data


@with_session
def get_assistant_simple_by_code_from_db(session, assistant_code: str) -> dict:
    filters = [WorkflowAssistantModel.code == assistant_code]
    assistant: WorkflowAssistantModel = session.query(WorkflowAssistantModel).filter(*filters).first()
    if assistant is None:
        return {}
    data = assistant.dict()
    return data
