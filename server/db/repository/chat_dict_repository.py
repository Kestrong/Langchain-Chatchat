from sqlalchemy import func

from server.db.models.chat_dict_model import ChatDictModel
from server.db.session import with_session


@with_session
def add_dict_to_db(session, dict_type: str, dict_value: str, dict_name: str, dict_name_cn: str, sort_id: int = 0):
    """
    添加字典项到数据库
    """
    c = ChatDictModel(dict_type=dict_type, dict_value=dict_value, dict_name=dict_name,
                      dict_name_cn=dict_name_cn, sort_id=sort_id)
    session.add(c)
    session.flush()
    return c.id


@with_session
def update_dict_to_db(session, dict_id: int, dict_type: str, dict_value: str, dict_name: str,
                      dict_name_cn: str, sort_id: int):
    """
    根据ID更新字典项
    """
    dict_item: ChatDictModel = session.query(ChatDictModel).filter(ChatDictModel.id == dict_id).first()
    if dict_item is not None:
        dict_item.dict_type = dict_type
        dict_item.dict_value = dict_value
        dict_item.dict_name = dict_name
        dict_item.dict_name_cn = dict_name_cn
        dict_item.sort_id = sort_id
    else:
        raise ValueError("ChatDict with id {} does not exist".format(dict_id))
    return dict_item.id


@with_session
def delete_dict_by_type_from_db(session, dict_type: str):
    """
    根据字典类型删除字典项
    """
    result = session.query(ChatDictModel).filter(ChatDictModel.dict_type == dict_type).delete()
    return result


@with_session
def delete_dict_by_id_from_db(session, dict_id: int):
    """
    根据字典ID删除字典项
    """
    session.query(ChatDictModel).filter(ChatDictModel.id == dict_id).delete()
    return dict_id


@with_session
def get_dicts_by_type_from_db(session, dict_type: str):
    """
    根据字典类型查询所有字典项
    """
    dicts = session.query(ChatDictModel).filter(ChatDictModel.dict_type == dict_type).order_by(
        ChatDictModel.sort_id.asc()).all()
    data = []
    for d in dicts:
        data.append(d.dict())
    return data


@with_session
def get_dicts_from_db(session, page: int = 1, size: int = 10, keyword: str = None, dict_type: str = None):
    """
    分页查询字典项
    """
    page_size = abs(size)
    page_num = max(page, 1)
    offset = (page_num - 1) * page_size

    filters = []
    if dict_type is not None and dict_type.strip() != '':
        filters.append(ChatDictModel.dict_type == dict_type)

    if keyword is not None and keyword.strip() != '':
        filters.append(func.concat(ChatDictModel.dict_type, ChatDictModel.dict_name,
                                   ChatDictModel.dict_name_cn, ChatDictModel.dict_value).ilike(
            '%{}%'.format(keyword)))

    dicts = (session.query(ChatDictModel).filter(*filters).order_by(
        ChatDictModel.dict_type.asc(), ChatDictModel.sort_id.asc()).offset(offset).limit(page_size).all())

    total = session.query(func.count(ChatDictModel.id)).filter(*filters).scalar()

    data = []
    for d in dicts:
        data.append(d.dict())
    return data, total
