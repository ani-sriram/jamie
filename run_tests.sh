#!/bin/bash
# Simple script to run Jamie agent tests using uv run

echo "🍽️  Starting Jamie Agent Test Suite with uv run"
echo "=================================================="

# Run the test script with uv run
uv run python run_jamie_tests.py

echo ""
echo "✅ Test execution completed!"
echo "📋 Check the logs/ directory for detailed results"
