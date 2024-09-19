from base64 import b64encode, b64decode

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from pydantic import BaseModel, Field

from server.agent.tools_select import register_tool
from server.memory.message_i18n import Message_I18N
from server.utils import get_tool_config


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
    key = bytes(key, encoding='utf-8')
    cipher = AES.new(key, AES.MODE_CBC, key)
    # 对消息进行填充
    padded_message = pad(text.encode(), AES.block_size)
    # 进行加密
    encrypted_bytes = cipher.encrypt(padded_message)
    # 将加密后的字节串转化为Base64编码的字符串
    encoded_cipher_text = b64encode(encrypted_bytes).decode()
    return encoded_cipher_text


def decrypt(text: str):
    key = get_tool_config().TOOL_CONFIG.get("aes", {}).get("key")
    key = bytes(key, encoding='utf-8')
    # 将Base64编码的字符串转化为字节串
    decoded_cipher_text = b64decode(text)
    cipher = AES.new(key, AES.MODE_CBC, key)
    # 解密
    decrypted_padded_bytes = cipher.decrypt(decoded_cipher_text)
    # 去除填充
    unpadded_decrypted_bytes = unpad(decrypted_padded_bytes, AES.block_size)
    # 将字节串转化为字符串
    decrypted_message = unpadded_decrypted_bytes.decode()
    return decrypted_message


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
