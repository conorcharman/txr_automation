#!/bin/bash
# Run all tests for the project

echo "Running all tests..."
echo "===================="
echo

# Run core library tests
echo "Testing core library..."
python -m pytest tests/test_core/ -v

# Run replay tests (when they exist)
if [ -d "tests/test_replay" ] && [ "$(ls -A tests/test_replay/*.py 2>/dev/null)" ]; then
    echo
    echo "Testing replay scripts..."
    python -m pytest tests/test_replay/ -v
fi

# Run accuracy testing tests (when they exist)
if [ -d "tests/test_accuracy_testing" ] && [ "$(ls -A tests/test_accuracy_testing/*.py 2>/dev/null)" ]; then
    echo
    echo "Testing accuracy testing scripts..."
    python -m pytest tests/test_accuracy_testing/ -v
fi

echo
echo "===================="
echo "All tests complete!"
