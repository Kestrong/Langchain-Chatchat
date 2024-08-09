import os
import shutil
from typing import BinaryIO, Iterable

from pathlib import Path

from configs.basic_config import logger
from server.knowledge_base.oss import OssType

try:
    from configs.kb_config import oss_config
except ImportError:
    oss_config = {}


def __get_file_path__(bucket_name: str, object_name: str):
    from server.knowledge_base.utils import get_file_path
    return get_file_path(bucket_name, object_name)


class Base:

    def __init__(self):
        self.oss_config = oss_config

    def type(self):
        return OssType.FILESYSTEM.value

    def object_exist(self, bucket_name: str, object_name: str) -> bool:
        file_path = __get_file_path__(bucket_name=bucket_name, object_name=object_name)
        if os.path.isfile(file_path):
            return True
        return False

    def object_stat(self, bucket_name: str, object_name: str) -> dict:
        file_path = __get_file_path__(bucket_name=bucket_name, object_name=object_name)
        if os.path.exists(file_path):
            file_stat = os.stat(file_path)
            return {"size": file_stat.st_size, "ctime": file_stat.st_ctime, "mtime": file_stat.st_mtime}
        return {}

    def object_url(self, bucket_name: str, object_name: str) -> str:
        return __get_file_path__(bucket_name=bucket_name, object_name=object_name)

    def put_object(self, data: BinaryIO, bucket_name: str, object_name: str, override: bool):
        file_path = __get_file_path__(bucket_name=bucket_name, object_name=object_name)
        with data as d:
            file_content = d.read()  # 读取上传文件的内容

            if not os.path.isdir(os.path.dirname(file_path)):
                os.makedirs(os.path.dirname(file_path))
            with open(file_path, "wb") as f:
                f.write(file_content)

    def get_object(self, bucket_name: str, object_name: str):
        file_path = __get_file_path__(bucket_name=bucket_name, object_name=object_name)
        return open(file_path, "rb")

    def fget_object(self, bucket_name: str, object_name: str, file_path: str):
        file_path_exist = __get_file_path__(bucket_name=bucket_name, object_name=object_name)
        if file_path != file_path_exist:
            parent_ddir = os.path.dirname(file_path)
            if not os.path.exists(parent_ddir):
                os.makedirs(parent_ddir, exist_ok=True)
            shutil.copyfile(file_path_exist, file_path)

    def delete_object(self, bucket_name: str, object_name: str) -> bool:
        try:
            file_path = __get_file_path__(bucket_name=bucket_name, object_name=object_name)
            if os.path.exists(file_path):
                os.remove(file_path)
            return True
        except Exception as e:
            logger.error(f'{e}')
            return False

    def list_objects(self, bucket_name: str) -> Iterable:

        def is_skiped_path(path: str):
            tail = os.path.basename(path).lower()
            for x in ["temp", "tmp", ".", "~$"]:
                if tail.startswith(x):
                    return True
            return False

        def process_entry(entry):
            if is_skiped_path(entry.path):
                return

            if entry.is_symlink():
                target_path = os.path.realpath(entry.path)
                with os.scandir(target_path) as target_it:
                    for target_entry in target_it:
                        process_entry(target_entry)
            elif entry.is_file():
                file_path = (Path(os.path.relpath(entry.path, bucket_name)).as_posix())  # 路径统一为 posix 格式
                return file_path
            elif entry.is_dir():
                with os.scandir(entry.path) as it:
                    for sub_entry in it:
                        process_entry(sub_entry)

        with os.scandir(bucket_name) as it:
            for entry in it:
                yield process_entry(entry)
