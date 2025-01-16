import sys

import pytest
import requests
from pathlib import Path
from sse_starlette import EventSourceResponse
from starlette.responses import Response

root_path = Path(__file__).parent.parent.parent
sys.path.append(str(root_path))
from configs.server_config import FSCHAT_MODEL_WORKERS
from server.utils import api_address, get_model_worker_config

from pprint import pprint
import random
from typing import List


def get_configured_models() -> List[str]:
    model_workers = list(FSCHAT_MODEL_WORKERS)
    if "default" in model_workers:
        model_workers.remove("default")
    return model_workers


api_base_url = api_address()


def get_running_models(api="/llm_model/list_models"):
    url = api_base_url + api
    r = requests.post(url)
    if r.status_code == 200:
        return r.json()["data"]
    return []


def test_running_models(api="/llm_model/list_running_models"):
    url = api_base_url + api
    r = requests.post(url)
    assert r.status_code == 200
    print("\n获取当前正在运行的模型列表：")
    pprint(r.json())
    assert isinstance(r.json()["data"], list)
    assert len(r.json()["data"]) > 0


# 不建议使用stop_model功能。按现在的实现，停止了就只能手动再启动
# def test_stop_model(api="/llm_model/stop"):
#     url = api_base_url + api
#     r = requests.post(url, json={""})


def test_change_model(api="/llm_model/change_model"):
    url = api_base_url + api

    running_models = get_running_models()
    assert len(running_models) > 0

    model_workers = get_configured_models()

    availabel_new_models = list(set(model_workers) - set(running_models))
    assert len(availabel_new_models) > 0
    print(availabel_new_models)

    local_models = [x for x in running_models if not get_model_worker_config(x).get("online_api")]
    model_name = random.choice(local_models)
    new_model_name = random.choice(availabel_new_models)
    print(f"\n尝试将模型从 {model_name} 切换到 {new_model_name}")
    r = requests.post(url, json={"model_name": model_name, "new_model_name": new_model_name})
    assert r.status_code == 200

    running_models = get_running_models()
    assert new_model_name in running_models


@pytest.mark.asyncio
async def test_workflow():
    from server.chat.workflow_chat import do_workflow_chat

    flow = {
        "nodes": [
            {
                "position": {"width": 10, "height": 10, "x": -1, "y": -1},
                "node": {
                    "id": "chat_input-eW9YZP",
                    "name": "chat_input",
                    "display_name": "Chat Input",
                    "description": "Get chat inputs from the Playground.",
                    "tag": "Input",
                    "type": "ChatInputComponent",
                    "inputs": [
                        {
                            "id": "query-388Thz",
                            "name": "query",
                            "display_name": "Text",
                            "required": True,
                            "info": "Message to be passed as input.",
                            "options": [],
                            "field_type": "str",
                            "value": "",
                            "type": "TextInput"
                        },
                        {
                            "id": "conversation_id-3ptUtp",
                            "name": "conversation_id",
                            "display_name": "Conversation ID",
                            "required": False,
                            "info": "The conversation id of the chat. If empty, will auto created.",
                            "options": [],
                            "field_type": "str",
                            "type": "TextInput"
                        },
                        {
                            "id": "store_message-LVXGV9",
                            "name": "store_message",
                            "display_name": "Store Message",
                            "required": False,
                            "info": "Store the message in the history.",
                            "options": [],
                            "field_type": "bool",
                            "value": True,
                            "type": "BooleanInput"
                        },
                        {
                            "id": "extra-japBe5",
                            "name": "extra",
                            "display_name": "Extra Inputs",
                            "required": False,
                            "info": "Extra inputs passed to the chat.",
                            "options": [],
                            "field_type": "dict",
                            "value": {},
                            "type": "DictInput"
                        }
                    ],
                    "outputs": []
                }
            },
            {
                "position": {"width": 10, "height": 10, "x": -1, "y": -1},
                "node": {
                    "id": "local_llm-3nRCf6",
                    "name": "local_llm",
                    "display_name": "Local LLM",
                    "description": "Generate text using Local LLMs.",
                    "tag": "Model",
                    "type": "LocalLLMComponent",
                    "inputs": [
                        {
                            "id": "query-62wToY",
                            "name": "query",
                            "display_name": "Text",
                            "required": True,
                            "info": "Message to be passed as input.",
                            "options": [],
                            "field_type": "str",
                            "value": "",
                            "type": "TextInput"
                        },
                        {
                            "id": "prompt-3JgZ6b",
                            "name": "prompt",
                            "display_name": "Prompt",
                            "required": False,
                            "info": "Prompt for chat.",
                            "options": [],
                            "field_type": "str",
                            "type": "TextInput"
                        },
                        {
                            "id": "model_name-ysicPV",
                            "name": "model_name",
                            "display_name": "Model Name",
                            "required": True,
                            "info": "The name of LLM, optional ['qwen-api'].",
                            "options": [
                                "qwen-api"
                            ],
                            "field_type": "str",
                            "value": "qwen-api",
                            "type": "TextInput"
                        },
                        {
                            "id": "max_tokens-3U5pDd",
                            "name": "max_tokens",
                            "display_name": "Max Tokens",
                            "required": False,
                            "info": "The maximum number of tokens to generate. Unlimited tokens if no set or set 0.",
                            "options": [],
                            "field_type": "int",
                            "type": "IntegerInput"
                        },
                        {
                            "id": "temperature-3SdeU8",
                            "name": "temperature",
                            "display_name": "Temperature",
                            "required": False,
                            "options": [],
                            "field_type": "float",
                            "value": 0.7,
                            "type": "FloatInput"
                        },
                        {
                            "id": "knowledge_base_names-K3WJQh",
                            "name": "knowledge_base_names",
                            "display_name": "KnowledgeBase Names",
                            "required": False,
                            "info": "Available knowledgebase names to use for LLM.",
                            "options": [
                                "inspection",
                                "faiss",
                                "milvus_local",
                                "samples"
                            ],
                            "field_type": "list",
                            "value": [],
                            "type": "ListInput"
                        },
                        {
                            "id": "tool_names-y4b2Ay",
                            "name": "tool_names",
                            "display_name": "Tool Names",
                            "required": False,
                            "info": "Available tool names to use for LLM.",
                            "options": [
                                "search_knowledgebase_complex",
                                "calculate",
                                "weathercheck",
                                "shell",
                                "search_internet",
                                "wolfram",
                                "search_youtube",
                                "arxiv",
                                "aes",
                                "text2sql",
                                "http_request"
                            ],
                            "field_type": "list",
                            "value": [],
                            "type": "ListInput"
                        },
                        {
                            "id": "api_names-3fGK97",
                            "name": "api_names",
                            "display_name": "Api Names",
                            "required": False,
                            "info": "Available api names to use for LLM.",
                            "options": [],
                            "field_type": "list",
                            "value": [],
                            "type": "ListInput"
                        }
                    ],
                    "outputs": [
                        {
                            "id": "answer-gRY6fN",
                            "name": "answer",
                            "type": "TextOutput",
                            "display_name": "Answer",
                            "field_type": "str"
                        },
                        {
                            "id": "docs-gRs6fN",
                            "name": "docs",
                            "type": "ListOutput",
                            "display_name": "Docs",
                            "field_type": "list"
                        },
                        {
                            "id": "thought-bRY6fN",
                            "name": "thought",
                            "type": "TextOutput",
                            "display_name": "Thought",
                            "field_type": "str"
                        }
                    ]
                }
            },
            {
                "position": {"width": 10, "height": 10, "x": -1, "y": -1},
                "node": {
                    "id": "chat_output-VkgPao",
                    "name": "chat_output",
                    "display_name": "Chat Output",
                    "description": "Get chat outputs from the Playground.",
                    "tag": "Output",
                    "type": "ChatOutputComponent",
                    "inputs": [],
                    "outputs": [
                        {
                            "id": "answer-3jFniQ",
                            "name": "answer",
                            "type": "TextOutput",
                            "display_name": "Answer",
                            "field_type": "str",
                            "value": "{{ local_llm-3nRCf6.outputs.answer }}"
                        }
                    ]
                }
            }
        ],
        "edges": [
            {
                "source": "chat_input-eW9YZP",
                "target": "local_llm-3nRCf6",
            },
            {
                "source": "local_llm-3nRCf6",
                "target": "chat_output-VkgPao",
            }
        ]
    }
    chat_response = await do_workflow_chat(query="你好", assistant_id=-1, extra={}, workflow_config=flow,
                                           stream=True, store_message=False)
    if isinstance(chat_response, EventSourceResponse):
        async for chunk in chat_response.body_iterator:
            print(chunk)
    elif isinstance(chat_response, Response):
        return {"answer": chat_response.body.decode('utf-8')}
    else:
        print(chat_response)
