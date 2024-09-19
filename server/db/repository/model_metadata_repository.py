from typing import List

from server.db.models.model_metadata import ModelMetadataModel
from server.db.session import with_session


@with_session
def get_model_metadata_from_db(session, model_name: str = None) -> dict:
    model_metadata: List[ModelMetadataModel] = session.query(
        ModelMetadataModel).all() if not model_name else session.query(
        ModelMetadataModel).filter(ModelMetadataModel.model_name == model_name).all()
    return {m.model_name: m.dict() for m in model_metadata}
