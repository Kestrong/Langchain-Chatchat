# shellcheck disable=SC2164
cd "${PROJECT_DIR}"
rm -rf logs/model_worker_*.log
cp -r ${PROJECT_DIR}/template/* ${PROJECT_DIR}/knowledge_base/samples/content/template/
python startup.py "${ARGS}"