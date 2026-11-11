#!/usr/bin/env bash
set -e
echo "========================================================"
echo "Running BigData Checkpoint 3: Spark Processing Pipeline"
echo "========================================================"
python src/pipeline.py --config config/config.json
