# shellcheck disable=SC2164
cd /llm/Lanchain-Chatchat
rm -rf logs/model_worker_*.log
python startup.py "${ARGS}"