import json
from typing import Dict, Any, Union, ClassVar

from common.exceptions import ChatBusinessException
from configs import LLM_MODELS, TEMPERATURE, VECTOR_SEARCH_TOP_K, SCORE_THRESHOLD
from server.db.repository import get_assistant_simple_by_code_from_db
from server.utils import api_address, get_httpx_client
from server.workflow.component.base.component import Component
from server.workflow.utils.event_manager import AsyncPubSub, SSEEvent, SSEEventType
from server.workflow.utils.inputs import TextInput, IntegerInput, FloatInput, ListInput
from server.workflow.utils.outputs import TextOutput, ListOutput, IntOutput


class LocalLLMComponent(Component):
    display_name = "${WORKFLOW_DISPLAYNAME_LOCALLLM}"
    description = "${WORKFLOW_DESCRIPTION_LOCALLLM}"
    name = "local_llm"
    tag = "${WORKFLOW_TAG_MODEL}"
    icon: Union[str, None]
    streamable: ClassVar[bool] = True

    inputs = [
        TextInput(
            name='query',
            display_name="${WORKFLOW_INPUT_DISPLAYNAME_QUERY}",
            required=True,
            info="${WORKFLOW_INPUT_INFO_QUERY}",
            value=''
        ),
        TextInput(
            name='assistant_code',
            display_name="${WORKFLOW_INPUT_DISPLAYNAME_ASSISTANT_CODE}",
            info="${WORKFLOW_INPUT_INFO_ASSISTANT_CODE}",
        ),
        TextInput(
            name='prompt',
            display_name="${WORKFLOW_INPUT_DISPLAYNAME_PROMPT}",
            info="${WORKFLOW_INPUT_INFO_PROMPT}",
        ),
        TextInput(
            name='model_name',
            display_name="${WORKFLOW_INPUT_DISPLAYNAME_MODEL_NAME}",
            required=True,
            info="${WORKFLOW_INPUT_INFO_MODEL_NAME}",
            options=LLM_MODELS,
            value=LLM_MODELS[0]
        ),
        IntegerInput(
            name='max_tokens',
            display_name="${WORKFLOW_INPUT_DISPLAYNAME_MAX_TOKENS}",
            info="${WORKFLOW_INPUT_INFO_MAX_TOKENS}",
        ),
        IntegerInput(
            name='history_len',
            display_name="${WORKFLOW_INPUT_DISPLAYNAME_HISTORY_LEN}",
            info="${WORKFLOW_INPUT_INFO_HISTORY_LEN}",
            value=-1
        ),
        IntegerInput(
            name='top_k',
            display_name="${WORKFLOW_INPUT_DISPLAYNAME_TOP_K}",
            info="${WORKFLOW_INPUT_INFO_TOP_K}",
            value=VECTOR_SEARCH_TOP_K
        ),
        FloatInput(
            name='score_threshold',
            display_name="${WORKFLOW_INPUT_DISPLAYNAME_SCORE_THRESHOLD}",
            info="${WORKFLOW_INPUT_INFO_SCORE_THRESHOLD}",
            value=SCORE_THRESHOLD
        ),
        FloatInput(
            name='temperature',
            display_name="${WORKFLOW_INPUT_DISPLAYNAME_TEMPERATURE}",
            value=TEMPERATURE
        ),
        TextInput(
            name='knowledge_id',
            display_name="${WORKFLOW_INPUT_DISPLAYNAME_KNOWLEDGE_ID}",
            info="${WORKFLOW_INPUT_INFO_KNOWLEDGE_ID}",
        ),
        ListInput(
            name='knowledge_base_names',
            display_name="${WORKFLOW_INPUT_DISPLAYNAME_KNOWLEDGE_BASE_NAMES}",
            info="${WORKFLOW_INPUT_INFO_KNOWLEDGE_BASE_NAMES}",
            options=[]
        ),
        ListInput(
            name='tool_names',
            display_name="${WORKFLOW_INPUT_DISPLAYNAME_TOOL_NAMES}",
            info="${WORKFLOW_INPUT_INFO_TOOL_NAMES}",
            options=[]
        ),
        ListInput(
            name='api_names',
            display_name="${WORKFLOW_INPUT_DISPLAYNAME_API_NAMES}",
            info="${WORKFLOW_INPUT_INFO_API_NAMES}",
        ),
    ]

    outputs = [
        TextOutput(
            display_name="${WORKFLOW_OUTPUT_DISPLAYNAME_ANSWER}",
            name="answer",
        ),
        ListOutput(
            display_name="${WORKFLOW_OUTPUT_DISPLAYNAME_DOCS}",
            name="docs",
        ),
        TextOutput(
            display_name="${WORKFLOW_OUTPUT_DISPLAYNAME_THOUGHT}",
            name="thought",
        ),
        IntOutput(
            display_name="${WORKFLOW_OUTPUT_DISPLAYNAME_TOTAL_TOKENS}",
            name="total_tokens",
        )
    ]

    async def _run(self, state: Dict[str, Any]):
        pubsub: AsyncPubSub = state.get("pubsub")
        try:
            inputs = self.get_context()[self.id]["inputs"]
            query = inputs.get("query") or state.get("query")
            extra = inputs.get("extra") or state.get("extra", {})
            conversation_id = state.get("conversation_id")
            knowledge_id = inputs.get("knowledge_id")
            assistant_code = inputs.get("assistant_code")
            assistant_id = -1
            if assistant_code:
                assistant = get_assistant_simple_by_code_from_db(assistant_code=assistant_code)
                if assistant and not assistant.get('workflow_config'):
                    assistant_id = assistant["id"]
            history_len = state.get("history_len") or -1
            stream = True
            store_message = False
            prompt = inputs.get("prompt") or state.get("prompt")
            if not prompt:
                prompt = "default"
            model_name = inputs.get("model_name")
            max_tokens = inputs.get("max_tokens") or -1
            temperature = inputs.get("temperature") or TEMPERATURE
            knowledge_base_names = inputs.get("knowledge_base_names")
            top_k = inputs.get("top_k") or VECTOR_SEARCH_TOP_K
            score_threshold = inputs.get("score_threshold") or SCORE_THRESHOLD
            tool_names = inputs.get("tool_names")
            api_names = inputs.get("api_names")
            api_base_url = api_address()
            data = dict(query=query, extra=extra, conversation_id=conversation_id,
                        default_value_from_assistant=False, assistant_id=assistant_id,
                        stream=stream, model_name=model_name, knowledge_id=knowledge_id,
                        temperature=temperature, max_tokens=max_tokens, history_len=history_len,
                        top_k=top_k, score_threshold=score_threshold,
                        prompt_name=prompt, knowledge_base_names=knowledge_base_names,
                        store_message=store_message, tool_names=tool_names,
                        api_names=api_names)
            result = {}
            answer = ''
            async with get_httpx_client(use_async=True) as client:
                async with client.stream("POST", url=f"{api_base_url}/chat/chat", json=data) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        event = json.loads(line[6:])
                        if pubsub:
                            event.pop("conversation_id", None)
                            event.pop("message_id", None)
                            await pubsub.publish(self.id, SSEEvent(SSEEventType.DATA, self.id, event))
                        if event.get("error"):
                            err = ChatBusinessException(event.get("answer"))
                            if event.get("error_info"):
                                err.__cause__ = ChatBusinessException(event.get("error_info"))
                            raise err
                        if "answer" in event:
                            answer += event["answer"]
                        if "msg" in event:
                            answer += event["msg"]
                        if "docs" in event:
                            result['docs'] = event["docs"]
                        if "thought" in event:
                            result['thought'] = event["thought"]
                        if "total_tokens" in event:
                            result['total_tokens'] = event["total_tokens"]
            result.setdefault("docs", [])
            result.setdefault("thought", None)
            result.setdefault("total_tokens", 0)
            result['answer'] = answer
            return result
        finally:
            if pubsub:
                await pubsub.publish(self.id, SSEEvent(SSEEventType.DONE, self.id, None))
