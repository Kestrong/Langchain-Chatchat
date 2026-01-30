from typing import List

from dateutil import parser

from server.db.models.model_metadata import ModelMetadataModel, ModelPerformanceMetricsModel
from server.db.session import with_session


@with_session
def get_model_metadata_from_db(session, model_name: str = None) -> dict:
    model_metadata: List[ModelMetadataModel] = session.query(
        ModelMetadataModel).all() if not model_name else session.query(
        ModelMetadataModel).filter(ModelMetadataModel.model_name == model_name).all()
    return {m.model_name: m.dict() for m in model_metadata}


@with_session
def add_performance_metrics_to_db(session, conversation_id: str, message_id: str, model_name: str, chat_type: str,
                                  start_time=None, first_token_latency: float = None, tokens_per_second: float = None,
                                  total_tokens: int = 0, total_time: float = None, end_time=None,
                                  extra_info: dict = None):
    performance_metric = ModelPerformanceMetricsModel(
        conversation_id=conversation_id,
        message_id=message_id,
        model_name=model_name,
        chat_type=chat_type,
        start_time=start_time,
        first_token_latency=first_token_latency,
        tokens_per_second=tokens_per_second,
        total_tokens=total_tokens,
        total_time=total_time,
        end_time=end_time,
        extra_info=extra_info or {}
    )
    session.add(performance_metric)


@with_session
def delete_performance_metrics_by_time(session, start_time: str = None, end_time: str = None):
    filters = []
    if start_time is not None and start_time != '':
        filters.append(ModelPerformanceMetricsModel.create_time >= parser.parse(start_time))
    if end_time is not None and end_time != '':
        filters.append(ModelPerformanceMetricsModel.create_time <= parser.parse(end_time))
    session.query(ModelPerformanceMetricsModel).filter(*filters).delete()
