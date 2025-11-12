import datetime
import urllib.parse
from io import BytesIO

from fastapi import Body, Query
from fastapi.responses import StreamingResponse
from openpyxl import Workbook

from configs.basic_config import logger, log_verbose
from server.db.repository.conversation_repository import add_conversation_to_db, update_conversation_to_db, \
    delete_conversation_from_db, get_conversation_from_db, delete_user_conversation_from_db, get_conversation_by_id, \
    metrics_db
from server.db.repository.message_repository import delete_message_from_db, \
    filter_message_page, list_user_feedback_messages
from server.memory.message_i18n import Message_I18N
from server.memory.token_info_memory import is_english
from server.utils import BaseResponse


def create_conversation(chat_type: str = Body(
    description="会话类型，可选值：llm_chat，knowledge_base_chat，search_engine_chat，agent_chat"),
        assistant_id: int = Body(description="助手ID"),
        name: str = Body(description="会话名称"),
        tag: str = Body(default="", description="会话标签")) -> BaseResponse:
    try:
        conversation_id = add_conversation_to_db(chat_type=chat_type, name=name, tag=tag, assistant_id=assistant_id)
    except Exception as e:
        msg = f"创建会话出错： {e}"
        logger.error(f'{e.__class__.__name__}: {msg}',
                     exc_info=e if log_verbose else None)
        return BaseResponse(code=500, msg=Message_I18N.API_CREATE_ERROR.value)
    return BaseResponse(code=200, data={'conversation_id': conversation_id})


def update_conversation(id: str = Body(description="会话id"),
                        name: str = Body(description="会话名称"),
                        tag: str = Body(default=None, description="会话标签，传null不更新")) -> BaseResponse:
    try:
        conversation_id = update_conversation_to_db(conversation_id=id, name=name, tag=tag)
    except Exception as e:
        msg = f"修改会话出错： {e}"
        logger.error(f'{e.__class__.__name__}: {msg}',
                     exc_info=e if log_verbose else None)
        return BaseResponse(code=500, msg=Message_I18N.API_UPDATE_ERROR.value)
    return BaseResponse(code=200, data={'conversation_id': conversation_id})


def delete_conversation(id: str = Query(description="会话id")) -> BaseResponse:
    try:
        conversation_id = delete_conversation_from_db(conversation_id=id)
    except Exception as e:
        msg = f"删除会话出错： {e}"
        logger.error(f'{e.__class__.__name__}: {msg}',
                     exc_info=e if log_verbose else None)
        return BaseResponse(code=500, msg=Message_I18N.API_DELETE_ERROR.value)
    return BaseResponse(code=200, data={'conversation_id': conversation_id})


def delete_user_conversation(assistant_id: int = Query(-1, description="助手ID")) -> BaseResponse:
    try:
        delete_user_conversation_from_db(assistant_id=assistant_id)
    except Exception as e:
        msg = f"删除用户会话出错： {e}"
        logger.error(f'{e.__class__.__name__}: {msg}',
                     exc_info=e if log_verbose else None)
        return BaseResponse(code=500, msg=Message_I18N.API_DELETE_ERROR.value)
    return BaseResponse(code=200, data={})


def filter_message(id: str = Query(description="会话id"),
                   page: int = Query(default=1, description="页码"),
                   limit: int = Query(default=10, description='消息数量')) -> BaseResponse:
    messages, total = filter_message_page(conversation_id=id, page=page, limit=min(abs(limit), 1000))
    for m in messages:
        metadata = m.get('meta_data')
        if metadata:
            if 'user' in metadata:
                del metadata['user']
            if 'api_key' in metadata:
                del metadata['api_key']
            m['meta_data'] = metadata
    return BaseResponse(code=200, data={'messages': messages, 'total': total})


def filter_conversation(assistant_id: int = Query(-1, description="助手ID"),
                        page: int = Query(default=1, description="页码"),
                        limit: int = Query(default=10, description='会话数量'),
                        start_time: str = Query(default=None, description='开始时间:yyyy-MM-dd HH:mm:ss'),
                        end_time: str = Query(default=None, description='结束时间:yyyy-MM-dd HH:mm:ss'),
                        keyword: str = Query(default=None, description="关键字搜索"),
                        tag: str = Query(default=None, description="会话标签")) -> BaseResponse:
    conversations, total = get_conversation_from_db(assistant_id=assistant_id, page=page, limit=min(abs(limit), 1000),
                                                    start_time=start_time, end_time=end_time, keyword=keyword, tag=tag)
    return BaseResponse(code=200, data={'conversations': conversations, 'total': total})


def get_conversation_detail(id: str = Query(description="会话id")) -> BaseResponse:
    conversation = get_conversation_by_id(conversation_id=id)
    return BaseResponse(code=200, data={'conversation': conversation})


def delete_message(message_id: str = Query(description="消息id")) -> BaseResponse:
    try:
        message_id = delete_message_from_db(message_id=message_id)
    except Exception as e:
        msg = f"删除消息出错： {e}"
        logger.error(f'{e.__class__.__name__}: {msg}',
                     exc_info=e if log_verbose else None)
        return BaseResponse(code=500, msg=Message_I18N.API_DELETE_ERROR.value)
    return BaseResponse(code=200, data={'message_id': message_id})


def list_feedback(query: str = Query(None, description="查询关键词"),
                  response: str = Query(None, description="回复关键词"),
                  assistant_name: str = Query(None, description="助手名称关键词"),
                  start_time: str = Query(None, description="开始时间:yyyy-MM-dd HH:mm:ss"),
                  end_time: str = Query(None, description="结束时间:yyyy-MM-dd HH:mm:ss"),
                  page: int = Query(1, description="页码"),
                  limit: int = Query(10, description="每页数量")) -> BaseResponse:
    try:
        messages, total = list_user_feedback_messages(
            query_keyword=query,
            response_keyword=response,
            assistant_name_keyword=assistant_name,
            start_time=start_time,
            end_time=end_time,
            page=page,
            limit=limit
        )
        english = is_english()
        for m in messages:
            if english:
                m["assistant_name"] = m.get("assistant_name_en") or m.get("assistant_name", "")
                m["feedback_type"] = "Thumbs Down" if m.get("feedback_score", 0) < 0 else "Thumbs Up"
            else:
                m["feedback_type"] = "点踩" if m.get("feedback_score", 0) < 0 else "点赞"
        return BaseResponse(code=200, data={'messages': messages, 'total': total})
    except Exception as e:
        msg = f"查询用户反馈消息出错： {e}"
        logger.error(f'{e.__class__.__name__}: {msg}',
                     exc_info=e if log_verbose else None)
        return BaseResponse(code=500, msg=Message_I18N.API_CREATE_ERROR.value)


def export_feedback_to_excel(query: str = Query(None, description="查询关键词"),
                             response: str = Query(None, description="回复关键词"),
                             assistant_name: str = Query(None, description="助手名称关键词"),
                             start_time: str = Query(None, description="开始时间:yyyy-MM-dd HH:mm:ss"),
                             end_time: str = Query(None, description="结束时间:yyyy-MM-dd HH:mm:ss")):
    try:
        english = is_english()

        # 创建一个生成器函数来流式处理数据
        def generate_excel():
            wb = Workbook()
            ws = wb.active
            ws.title = "用户反馈消息" if not english else "User Feedback Messages"

            # 添加表头
            if english:
                headers = ["No.", "Scenario", "Query", "Response", "Feedback Type", "Feedback", "Feedback Time"]
            else:
                headers = ["序号", "使用场景", "问题", "回复", "类型", "反馈", "反馈时间"]
            ws.append(headers)

            # 分批处理数据以减少内存占用，最多导出10000条记录
            page = 1
            limit = 1000  # 每批处理1000条记录
            index = 1
            max_records = 10000  # 最多导出10000条记录

            while index <= max_records:
                messages, _ = list_user_feedback_messages(
                    query_keyword=query,
                    response_keyword=response,
                    assistant_name_keyword=assistant_name,
                    start_time=start_time,
                    end_time=end_time,
                    page=page,
                    limit=limit,
                    count=False
                )

                if not messages:
                    break

                # 处理数据行
                for message in messages:
                    # 如果已达到最大记录数限制，则停止处理
                    if index > max_records:
                        break

                    # 处理中英文切换
                    if english:
                        assistant_name_val = message.get("assistant_name_en") or message.get("assistant_name", "")
                        type_val = "Thumbs Down" if message.get("feedback_score", 0) < 0 else "Thumbs Up"
                    else:
                        assistant_name_val = message.get("assistant_name", "")
                        type_val = "点踩" if message.get("feedback_score", 0) < 0 else "点赞"
                    feedback_time = message.get("feedback_time")
                    ws.append([
                        index,
                        assistant_name_val,
                        message.get("query", ""),
                        message.get("response", ""),
                        type_val,
                        message.get("feedback_reason", ""),
                        feedback_time.strftime('%Y-%m-%d %H:%M:%S') if feedback_time else None,
                    ])
                    index += 1

                page += 1

                # 如果当前批次少于限制数量，说明已经处理完所有数据
                if len(messages) < limit:
                    break

            # 将Excel文件保存到内存中并返回
            excel_buffer = BytesIO()
            wb.save(excel_buffer)
            excel_buffer.seek(0)
            yield excel_buffer.getvalue()

        # 返回文件响应
        filename = f"用户反馈消息-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx" if not english else \
            f"User_Feedback_Messages-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx"
        filename = urllib.parse.quote(filename.encode('utf-8'))
        return StreamingResponse(
            generate_excel(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{filename}"
            }
        )
    except Exception as e:
        msg = f"导出用户反馈消息到Excel出错： {e}"
        logger.error(f'{e.__class__.__name__}: {msg}', exc_info=e if log_verbose else None)
        return BaseResponse(code=500, msg=Message_I18N.COMMON_CALL_FAILED.value)


def metrics(start_time: str = Query(None, description="开始时间:yyyy-MM-dd HH:mm:ss"),
            end_time: str = Query(None, description="结束时间:yyyy-MM-dd HH:mm:ss"),
            assistant_ids: str = Query(default=None, description="助手id列表"),
            ) -> BaseResponse:
    logger.debug(f"start_time: {start_time}, end_time:{end_time}")
    data = metrics_db(start_time=start_time, end_time=end_time, assistant_ids=assistant_ids)
    return BaseResponse(code=200, data=data)
