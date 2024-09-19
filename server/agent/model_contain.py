from contextvars import ContextVar


class ModelContainer:
    def __init__(self):
        self.MODEL = None
        self.TOOL_CONFIG: dict = {}


# 创建一个线程本地变量
model_container_context = ContextVar[ModelContainer]('model_container', default=None)


def get_model_container() -> ModelContainer:
    return model_container_context.get()


def create_model_container() -> ModelContainer:
    if model_container_context.get() is None:
        model_container_context.set(ModelContainer())
    return model_container_context.get()
