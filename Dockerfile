#python310_cuda:11.7.1-cudnn8-runtime-ubuntu22.04

#docker run -d --gpus all --name python-langchain-chatchat -it -v /data01/cloud-data/llm:/llm -p 20001:20001 -p 20000:20000 -p 20002:20002 -p 7861:7861 -p 8501:8501 -e MODEL_ROOT_PATH='/llm/models' -e KB_ROOT_PATH='/llm/knowledges'  python-langchain-chatchat:1.0.0 /bin/sh

FROM python-langchain-chatchat:1.0.0
MAINTAINER "KeStrong"<kestrong@foxmail.com>
LABEL authors="kesc"
ENV MODEL_ROOT_PATH='/llm/lanchain-chatchat/model_data' KB_ROOT_PATH='/llm/knowledges' EMBEDDING_DEVICE='auto' LLM_DEVICE='auto'
ENV ARGS="-a"
COPY /Lanchain-Chatchat /llm/lanchain-chatchat
CMD  ["sh", "/llm/lanchain-chatchat/boot-server-on-docker.sh"]