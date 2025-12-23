#!/bin/bash
# Run tests with coverage report

echo "Running tests with coverage..."
echo "=============================="
echo

python -m pytest tests/ --cov=src --cov-report=html --cov-report=term

echo
echo "=============================="
echo "Coverage report generated in htmlcov/index.html"
