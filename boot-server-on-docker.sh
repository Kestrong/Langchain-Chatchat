# shellcheck disable=SC2164
cd "${PROJECT_DIR}"
rm -rf logs/model_worker_*.log
python startup.py "${ARGS}"