@echo off
echo ========================================================
echo Running BigData Checkpoint 3: Spark Processing Pipeline
echo ========================================================
.venv\Scripts\python.exe src\pipeline.py --config config\config.json
pause
