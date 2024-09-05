import json
import time
import uuid
from typing import List, Dict, Literal

from fastchat import conversation as conv
from fastchat.conversation import Conversation
from websocket._core import create_connection

from configs import logger
from server.model_workers import ApiModelWorker, ApiChatParams


class QimingWorker(ApiModelWorker):

    def __init__(
            self,
            *,
            model_names: List[str] = ["qiming-api"],
            controller_addr: str = None,
            worker_addr: str = None,
            version: Literal["MaaS-Ws-v2"] = "MaaS-Ws-v2",
            **kwargs,
    ):
        kwargs.update(model_names=model_names, controller_addr=controller_addr, worker_addr=worker_addr)
        super().__init__(**kwargs)
        self.version = version

    def do_chat(self, params: ApiChatParams) -> Dict:
        params = params.load_config(self.model_names[0])
        uri = params.api_proxy
        xappid = params.api_key
        xappkey = params.secret_key
        timestamp = str(int(round(time.time() * 1000)))
        seqid = str(uuid.uuid1())
        headers = {"X-APP-ID": xappid, "X-APP-KEY": xappkey}
        """
        ------   问答场景输入参数描述   ------
            1、规章制度:param1用户问题,param2预留字段不使用,scene固定值8;\n
            2、综维问答:param1用户问题,param2预留字段不使用,scene固定值2;\n
            3、无线网优:param1用户问题,param2知识库检索开关。“true”：启用知识库检索功能,“false”：关闭知识库检索功能,scene固定值3;\n
            4、装维问答:param1用户角色，可填写：装维一线、客支、客调、客服、客户,param2用户问题,scene固定值7;\n
            5、故障复盘:param1固定为1，代表事故复盘,param2用户问题,scene固定值6;\n
            6、传输故障处置:param1故障现象,param2故障描述,scene固定值1;\n
            7、运维助手：param1用户问题,param2细分场景标识符，可填写：变更操作管控bgczgk、故障诊断gzzd、安全漏洞修复aqldxf、故障自愈gzzy、运维规范问答ywgfwd、服务台/翼问赋能fwt，scene固定值9;\n
            8、天翼云知识助手：param1用户问题,param2固定statecolud,scene固定值13;\n
        """
        message = {
            "uid": xappid,
            "timestamp": timestamp,
            "seqid": seqid,
            "stream": "true",
            "prov": params.role_meta['prov'],
            "session_id": seqid,
            "param1": "",
            "param2": "",
            "param3": "",
            "param4": "",
            "param5": "",
            "param6": "",
            "scene": ""
        }
        websocket = None
        text = ''
        stream = True
        try:
            content = params.messages[-1].get('content')
            if content.startswith('{') and content.endswith('}'):
                contentObj = json.loads(content)
                stream = contentObj.get('stream', True)
                if contentObj.get('question', '').startswith('###') and contentObj.get('question', '').endswith('###'):
                    parts = contentObj.get('question', '').split('###')
                    message['scene'] = parts[1]
                    message['param1'] = parts[2]
                    message['param2'] = parts[3] if len(parts) > 3 else ""
                else:
                    scene = contentObj.get('scene', '')
                    message['scene'] = scene
                    if scene in ['2', '8']:
                        message['param1'] = contentObj.get('question', '')
                    elif scene == '3':
                        message['param1'] = contentObj.get('question', '')
                        message['param2'] = 'true'
                    elif scene == '7':
                        message['param1'] = contentObj.get('role', '')
                        message['param2'] = contentObj.get('question', '')
                    elif scene == '6':
                        message['param1'] = '1'
                        message['param2'] = contentObj.get('question', '')
                    elif scene == '9':
                        message['param1'] = contentObj.get('question', '')
                        message['param2'] = contentObj.get('iTSubScene', contentObj.get('role', ''))
                    elif scene == '13':
                        message['param1'] = contentObj.get('question', '')
                        message['param2'] = 'statecolud'
                    else:
                        message['param1'] = contentObj.get('question', '')
                        message['param2'] = contentObj.get('description', '')
            else:
                parts = content.split('###')
                message['scene'] = parts[1]
                message['param1'] = parts[2]
                message['param2'] = parts[3] if len(parts) > 3 else ""
            websocket = create_connection(url=uri, header=headers, timeout=params.role_meta.get("timeout", 30))
            websocket.send(json.dumps(message))
            while True:
                response = websocket.recv()
                if response == "<#END>":
                    break
                text += response
                if stream:
                    yield {"error_code": 0, "text": text}
            if not stream:
                yield {"error_code": 0, "text": text}
        except Exception as e:
            logger.error(f"{e}")
            if text == '':
                yield {"error_code": 0, "text": "调用启明大模型失败或者启明大模型没有任何回复内容。"}
            else:
                if not stream:
                    yield {"error_code": 0, "text": text}
        finally:
            try:
                if websocket is not None:
                    websocket.close()
            except Exception:
                pass

    def get_embeddings(self, params):
        print("get_embedding")
        print(params)

    def make_conv_template(self, conv_template: str = None, model_path: str = None) -> Conversation:
        return conv.Conversation(
            name=self.model_names[0],
            system_message="",
            messages=[],
            roles=["user", "assistant", "system"],
            sep="\n### ",
            stop_str="###",
        )
