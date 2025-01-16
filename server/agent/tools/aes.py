from pydantic import BaseModel, Field

from server.agent.tools_select import register_tool
from server.memory.message_i18n import Message_I18N
from server.utils import get_tool_config, aes_encrypt, aes_decrypt


class AesInput(BaseModel):
    text: str = Field(description="text to encrypt or decrypt")
    cypher_mode: str = Field(description="cypher mode")


@register_tool(title="Aes文本加密",
               description="Use this tool to encrypt or decrypt text, the param 'cypher_mode' must be on of ['encrypt', 'decrypt']",
               args_schema=AesInput)
def aes(text: str, cypher_mode: str) -> str:
    if cypher_mode == "encrypt":
        return encrypt(text)
    elif cypher_mode == "decrypt":
        return decrypt(text)
    else:
        return Message_I18N.TOOL_AES_CYPHER_MODE_ERROR.value.format(cypher_mode=cypher_mode)


def encrypt(text: str) -> str:
    key = get_tool_config().TOOL_CONFIG.get("aes", {}).get("key")
    return aes_encrypt(text=text, key=key)


def decrypt(text: str):
    key = get_tool_config().TOOL_CONFIG.get("aes", {}).get("key")
    return aes_decrypt(text=text, key=key)


def decrypt_placeholder(text: str):
    if text.startswith("ENC(") and text.endswith(")"):
        return decrypt(text[4:-1])
    return text


if __name__ == '__main__':
    text = "你好"
    encrypted_text = encrypt(text)
    print(encrypted_text)
    print(decrypt(encrypted_text))
    print(decrypt_placeholder(encrypted_text))
    print(decrypt_placeholder(f"ENC({encrypted_text})"))
