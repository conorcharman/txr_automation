#!/bin/bash
# Run tests with coverage report

# Check if conda environment is activated
if [ -z "$CONDA_DEFAULT_ENV" ] || [ "$CONDA_DEFAULT_ENV" != "txr_automation" ]; then
    echo "ERROR: Conda environment 'txr_automation' is not activated"
    echo "Please run: conda activate txr_automation"
    exit 1
fi

echo "Running tests with coverage..."
echo "=============================="
echo

python -m pytest tests/ --cov=src --cov-report=html --cov-report=term

echo
echo "=============================="
echo "Coverage report generated in htmlcov/index.html"
