from typing import Dict, Any, Union

from server.chat.file_chat import _parse_files_in_thread
from server.knowledge_base.oss import default_oss
from server.workflow.component.base.component import Component
from server.workflow.utils.inputs import TextInput
from server.workflow.utils.outputs import ListOutput


class DocumentExtractorComponent(Component):
    display_name = "${WORKFLOW_DISPLAYNAME_DOCUMENTEXTRACTOR}"
    description = "${WORKFLOW_DESCRIPTION_DOCUMENTEXTRACTOR}"
    name = "document_extractor"
    tag = "${WORKFLOW_TAG_TOOL}"
    icon: Union[str, None]

    inputs = [
        TextInput(
            name='knowledge_id',
            display_name="${WORKFLOW_INPUT_DISPLAYNAME_KNOWLEDGE_ID}",
            info="${WORKFLOW_INPUT_INFO_KNOWLEDGE_ID}",
        ),
    ]

    outputs = [
        ListOutput(
            name='document',
            display_name="${WORKFLOW_OUTPUT_DISPLAYNAME_DOCUMENT}",
        )
    ]

    async def _run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        inputs = self.get_context()[self.id]["inputs"]
        knowledge_id = inputs.get("knowledge_id")
        document = []
        if knowledge_id:
            attachment_names = default_oss().list_objects(bucket_name="temp", object_name=knowledge_id)
            if attachment_names:
                for success, file, msg, part_docs in _parse_files_in_thread(files=attachment_names, dir=knowledge_id,
                                                                            doc=True):
                    if success:
                        content = "\n".join([doc.page_content for doc in part_docs])
                        document.append({"name": file, "content": content})
                    else:
                        document.append({"name": file, "content": "", "msg": msg})
        return {"document": document}
