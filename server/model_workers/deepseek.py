from typing import List, Literal

from server.model_workers import QwenWorker


class DeepSeekWorker(QwenWorker):

    def __init__(
            self,
            *,
            version: Literal["deepseek-r1"] = "deepseek-r1",
            model_names: List[str] = ["deepseek-api"],
            controller_addr: str = None,
            worker_addr: str = None,
            **kwargs,
    ):
        kwargs.update(model_names=model_names, controller_addr=controller_addr, worker_addr=worker_addr)
        kwargs.setdefault("context_len", 16384)
        super().__init__(**kwargs)
        self.version = version
