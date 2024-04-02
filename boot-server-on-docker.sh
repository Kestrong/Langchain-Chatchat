cd /llm/Lanchain-Chatchat
rm -rf logs
python copy_config_example.py prod
python startup.py ${ARGS}