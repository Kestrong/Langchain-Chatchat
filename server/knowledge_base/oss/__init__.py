from server.knowledge_base.oss.oss_type import OssType
from server.knowledge_base.oss.base import Base
from server.knowledge_base.oss.minio_oss import MinioOss


oss_base = Base()
oss_factory = {OssType.FILESYSTEM.value: oss_base}

if OssType.MINIO.value in oss_base.oss_config and oss_base.oss_config[OssType.MINIO.value].get("enabled"):
    try:
        oss_factory[OssType.MINIO.value] = MinioOss()
    except Exception as e:
        print(e)


def default_oss() -> Base:
    return oss_factory[oss_base.oss_config.get("default_type", OssType.FILESYSTEM)]


def get_oss(type: OssType) -> Base:
    return oss_factory[type.value]
