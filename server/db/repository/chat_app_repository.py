from sqlalchemy import func, or_

from server.db.models.chat_app_model import ChatAppModel
from server.db.session import with_session


@with_session
def add_app_to_db(session, name: str, name_en: str, api_key: str, secret_key: str, expired_time=None):
    app = ChatAppModel(name=name, name_en=name_en, api_key=api_key, secret_key=secret_key, expired_time=expired_time)
    session.add(app)
    session.flush()
    return app.id


@with_session
def update_app_to_db(session, app_id: int, name: str, name_en: str, api_key: str, secret_key: str, expired_time=None):
    app: ChatAppModel = session.query(ChatAppModel).filter(ChatAppModel.id == app_id).first()
    if app is not None:
        app.name = name
        app.name_en = name_en
        app.api_key = api_key
        app.secret_key = secret_key
        app.expired_time = expired_time
    else:
        raise ValueError("ChatApp with id {} does not exist".format(app_id))
    return app.id


@with_session
def delete_app_from_db(session, app_id: int):
    session.query(ChatAppModel).filter(ChatAppModel.id == app_id).delete()
    return app_id


@with_session
def get_app_from_db(session, page: int = 1, size: int = 10, keyword: str = None):
    page_size = abs(size)
    page_num = max(page, 1)
    offset = (page_num - 1) * page_size

    filters = []
    if keyword is not None and keyword.strip() != '':
        filters.append(or_(ChatAppModel.name.ilike('%{}%'.format(keyword)),
                           ChatAppModel.name_en.ilike('%{}%'.format(keyword))))

    apps = (session.query(ChatAppModel).filter(*filters)
            .order_by(ChatAppModel.create_time.desc()).offset(offset).limit(page_size).all())
    total = session.query(func.count(ChatAppModel.id)).filter(*filters).scalar()

    data = []
    for app in apps:
        data.append(app.dict())
    return data, total


@with_session
def get_app_by_api_key_from_db(session, api_key: str):
    app: ChatAppModel = session.query(ChatAppModel).filter(ChatAppModel.api_key == api_key).first()
    if app is None:
        return None
    return app.dict()


@with_session
def get_app_detail_from_db(session, app_id: int):
    app: ChatAppModel = session.query(ChatAppModel).filter(ChatAppModel.id == app_id).first()
    if app is None:
        return None
    return app.dict()
