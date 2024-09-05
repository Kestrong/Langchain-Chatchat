import os
from typing import BinaryIO, Iterable

from minio import Minio
from minio.deleteobjects import DeleteObject

from configs.basic_config import logger
from server.knowledge_base.oss import OssType
from server.knowledge_base.oss.base import Base


class MinioOss(Base):

    def __init__(self):
        super().__init__()
        self.config = self.oss_config.get("minio", {})
        self.bucket_name = self.config.get('default_bucket_name')
        self.minio = Minio(endpoint=self.config.get("endpoint"), access_key=self.config.get("access_key"),
                           secret_key=self.config.get("secret_key"), secure=self.config.get("secure"),
                           cert_check=self.config.get("secure"))
        if self.bucket_name:
            try:
                if not self.minio.bucket_exists(self.bucket_name):
                    self.minio.make_bucket(self.bucket_name)
            except Exception:
                pass

    def type(self):
        return OssType.MINIO.value

    def get_bucket_and_object(self, bucket_name: str, object_name: str):
        if self.bucket_name:
            return self.bucket_name, os.path.join(bucket_name, "content", object_name).replace("\\", "/")
        return bucket_name, os.path.join("content", object_name).replace("\\", "/")

    def object_exist(self, bucket_name: str, object_name: str) -> bool:
        try:
            bucket_name, object_name = self.get_bucket_and_object(bucket_name, object_name)
            object_stat = self.minio.stat_object(bucket_name, object_name)
            if object_stat is not None and object_stat.object_name:
                return True
        except Exception as e:
            logger.error(f'{e}')
            return False

    def object_stat(self, bucket_name: str, object_name: str) -> dict:
        bucket_name, object_name = self.get_bucket_and_object(bucket_name, object_name)
        object_stat = self.minio.stat_object(bucket_name, object_name)
        if object_stat is not None and object_stat.object_name:
            return {"size": object_stat.size, "ctime": object_stat.last_modified.timestamp(),
                    "mtime": object_stat.last_modified.timestamp()}
        return {}

    def object_url(self, bucket_name: str, object_name: str) -> str:
        bucket_name, object_name = self.get_bucket_and_object(bucket_name, object_name)
        return self.minio.get_presigned_url(method="get", bucket_name=bucket_name, object_name=object_name)

    def put_object(self, data: BinaryIO, bucket_name: str, object_name: str, override: bool):
        with data as d:
            bucket_name, object_name = self.get_bucket_and_object(bucket_name, object_name)
            self.minio.put_object(bucket_name=bucket_name, object_name=object_name, data=d, length=-1,
                                  part_size=1024 * 1024 * 5)

    def get_object(self, bucket_name: str, object_name: str):
        bucket_name, object_name = self.get_bucket_and_object(bucket_name, object_name)
        return self.minio.get_object(bucket_name, object_name)

    def fget_object(self, bucket_name: str, object_name: str, file_path: str):
        bucket_name, object_name = self.get_bucket_and_object(bucket_name, object_name)
        return self.minio.fget_object(bucket_name, object_name, file_path)

    def delete_object(self, bucket_name: str, object_name: str):
        try:
            new_bucket_name, new_object_name = self.get_bucket_and_object(bucket_name, object_name)
            delete_object_list = list(
                map(
                    lambda x: DeleteObject(str(os.path.join(new_object_name, x)).replace("\\", "/")),
                    self.list_objects(
                        bucket_name,
                        object_name,
                    ),
                )
            )
            delete_object_list.append(DeleteObject(new_object_name))
            errors = self.minio.remove_objects(new_bucket_name, delete_object_list)
            for error in errors:
                logger.error("error occurred when deleting object", error)
            return True
        except Exception as e:
            logger.error(f'{e}')
            return False

    def list_objects(self, bucket_name: str, object_name: str) -> Iterable:
        bucket_name, object_name = self.get_bucket_and_object(bucket_name, object_name)
        prefix = None
        if object_name:
            prefix = object_name if object_name.endswith("/") else f"{object_name}/"
        for o in self.minio.list_objects(bucket_name=bucket_name,
                                         prefix=prefix,
                                         recursive=True):
            yield o.object_name.replace(prefix, "")
