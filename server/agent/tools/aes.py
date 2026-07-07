from pydantic import BaseModel, Field

from server.agent.tools_select import register_tool
from server.memory.message_i18n import Message_I18N
from server.utils import aes_encrypt, aes_decrypt, get_tool_config, aes_decrypt_placeholder


class AesInput(BaseModel):
    text: str = Field(description="text to be encrypted or decrypted")
    cypher_mode: str = Field(description="cypher mode must be one of ['encrypt', 'decrypt']")


@register_tool(title="Aes文本加密",
               description="Use this tool to encrypt or decrypt text.",
               args_schema=AesInput)
def aes(tool_config: dict, text: str, cypher_mode: str) -> str:
    if cypher_mode == "encrypt":
        return encrypt(tool_config, text)
    elif cypher_mode == "decrypt":
        return decrypt(tool_config, text)
    else:
        return Message_I18N.TOOL_AES_CYPHER_MODE_ERROR.value.format(cypher_mode=cypher_mode)


def encrypt(tool_config: dict, text: str) -> str:
    key = tool_config.get("key")
    return aes_encrypt(text=text, key=key)


def decrypt(tool_config: dict, text: str):
    key = tool_config.get("key")
    return aes_decrypt(text=text, key=key)


def decrypt_placeholder(text: str):
    key = get_tool_config().TOOL_CONFIG.get("aes", {}).get("key")
    return aes_decrypt_placeholder(text=text, key=key)


if __name__ == '__main__':
    text = "你好"
    tool_config = get_tool_config().TOOL_CONFIG.get("aes", {})
    encrypted_text = encrypt(tool_config, text)
    print(encrypted_text)
    print(decrypt(tool_config, encrypted_text))
    print(decrypt_placeholder(encrypted_text))
    print(decrypt_placeholder(f"ENC({encrypted_text})"))
