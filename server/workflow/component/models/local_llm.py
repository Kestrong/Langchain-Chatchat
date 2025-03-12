import json
from typing import Dict, Any, Union

from common.exceptions import ChatBusinessException
from configs import LLM_MODELS, TEMPERATURE, VECTOR_SEARCH_TOP_K, SCORE_THRESHOLD
from server.agent.tools_select import get_all_tools
from server.db.repository import list_kbs_from_db
from server.utils import api_address, get_httpx_client
from server.workflow.component.base.component import Component
from server.workflow.utils.inputs import TextInput, IntegerInput, FloatInput, ListInput
from server.workflow.utils.outputs import TextOutput, ListOutput


class LocalLLMComponent(Component):
    display_name = "Local LLM"
    description = "Generate text using Local LLMs."
    name = "local_llm"
    tag = "Model"
    icon: Union[str, None]

    inputs = [
        TextInput(
            name='query',
            display_name='Text',
            required=True,
            info='Message to be passed as input.',
            value=''
        ),
        TextInput(
            name='prompt',
            display_name='Prompt',
            info='Prompt for chat.'
        ),
        TextInput(
            name='model_name',
            display_name='Model Name',
            required=True,
            info=f'The name of LLM, optional {LLM_MODELS}.',
            options=LLM_MODELS,
            value=LLM_MODELS[0]
        ),
        IntegerInput(
            name='max_tokens',
            display_name='Max Tokens',
            info='The maximum number of tokens to generate. Unlimited tokens if no set or set 0.'
        ),
        IntegerInput(
            name='top_k',
            display_name='TopK',
            info='The maximum number of knowledge base doc to match.',
            value=VECTOR_SEARCH_TOP_K
        ),
        FloatInput(
            name='score_threshold',
            display_name='Score Threshold',
            info='For the knowledge base match relevance threshold, the value range is between 0 and 1, where a smaller SCORE indicates higher relevance, and a SCORE of 1 is equivalent to no filtering. It is recommended to set this threshold around 0.5.',
            value=SCORE_THRESHOLD
        ),
        FloatInput(
            name='temperature',
            display_name='Temperature',
            value=TEMPERATURE
        ),
        ListInput(
            name='knowledge_base_names',
            display_name='KnowledgeBase Names',
            info='Available knowledgebase names to use for LLM.',
            options=[k["kb_name"] for k in list_kbs_from_db(all_kbs=True)[0]]
        ),
        ListInput(
            name='tool_names',
            display_name='Tool Names',
            info='Available tool names to use for LLM.',
            options=[t.name for t in get_all_tools()]
        ),
        ListInput(
            name='api_names',
            display_name='Api Names',
            info='Available api names to use for LLM.'
        ),
    ]

    outputs = [
        TextOutput(
            display_name="Answer",
            name="answer",
        ),
        ListOutput(
            display_name="Docs",
            name="docs",
        ),
        TextOutput(
            display_name="Thought",
            name="thought",
        )
    ]

    async def _run(self, state: Dict[str, Any]):

        inputs = super()._context[self.id]["inputs"]
        query = inputs.get("query") or state.get("query")
        extra = inputs.get("extra") or state.get("extra", {})
        conversation_id = state.get("conversation_id")
        assistant_id = state.get("assistant_id")
        history_len = state.get("history_len") or -1
        stream = False
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
                    stream=stream, model_name=model_name,
                    temperature=temperature, max_tokens=max_tokens, history_len=history_len,
                    top_k=top_k, score_threshold=score_threshold,
                    prompt_name=prompt, knowledge_base_names=knowledge_base_names,
                    store_message=store_message, tool_names=tool_names,
                    api_names=api_names)
        result = {}
        answer = ''
        with get_httpx_client() as client:
            response = client.post(url=f"{api_base_url}/chat/chat", json=data)
            for line in response.iter_lines():
                if not line:
                    continue
                event = json.loads(line[6:])
                if event.get("error"):
                    raise ChatBusinessException(event.get("answer"))
                if "answer" in event:
                    answer += event["answer"]
                elif "msg" in event:
                    answer += event["msg"]
                elif "docs" in event:
                    result['docs'] = event["docs"]
                elif "thought" in event:
                    result['thought'] = event["thought"]
        result.setdefault("docs", [])
        result.setdefault("thought", None)
        result['answer'] = answer
        return result
