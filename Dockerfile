#docker run -d --gpus all --name flm-chat -it -v /data01/cloud-data/llm:/llm -p 7861:7861 -p 8501:8501 -e TZ="Asia/Shanghai" -e MODEL_ROOT_PATH='/llm/models' -e KB_ROOT_PATH='/llm/knowledges'  flm-chat:1.0.0-snapshot /bin/sh

FROM flm-chat:1.0.0-snapshot
MAINTAINER "KeStrong"<kestrong@foxmail.com>
LABEL authors="kesc"
ENV TZ="Asia/Shanghai"
ENV MODEL_ROOT_PATH='/llm/models' KB_ROOT_PATH='/llm/knowledges' EMBEDDING_DEVICE='auto' LLM_DEVICE='auto'
ENV ARGS="-a"
ENV PROJECT_DIR="/llm/projects/gops-chat"
COPY /Lanchain-Chatchat ${PROJECT_DIR}/
CMD sh "${PROJECT_DIR}/boot-server-on-docker.sh"