import requests
from urllib3.exceptions import InsecureRequestWarning

# 全局禁用 InsecureRequestWarning 警告
requests.urllib3.disable_warnings(InsecureRequestWarning)

from .base import *
from .zhipu import ChatGLMWorker
from .minimax import MiniMaxWorker
from .xinghuo import XingHuoWorker
from .qianfan import QianFanWorker
from .fangzhou import FangZhouWorker
from .qwen import QwenWorker
from .baichuan import BaiChuanWorker
from .azure import AzureWorker
from .tiangong import TianGongWorker
from .gemini import GeminiWorker
from .claude import ClaudeWorker
from .qiming import QimingWorker
from .dify import DifyWorker
from .lingxi_fault import LingxiFaultWorker
from .lingxi_cutover import LingxiCutOverWorker
from .fastgpt import FastgptWorker
from .fuxi import FuXiWorker
from .deepseek import DeepSeekWorker
