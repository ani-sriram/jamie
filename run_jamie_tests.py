#!/usr/bin/env python3
"""
Simple script to run Jamie agent tests with comprehensive logging.
This script runs all the multi-turn conversation tests and generates detailed logs.
"""

import sys
import os
from pathlib import Path

# Add src to Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

# Import test module
from tests.test_jamie import TestJamieAgent


def main():
    """Run all Jamie agent tests"""
    print("🍽️  Starting Jamie Agent Test Suite")
    print("=" * 50)

    # Create test instance
    test_instance = TestJamieAgent()

    try:
        # Create agent and logger directly (not using pytest fixtures)
        from agent.graph import JamieAgent
        import logging
        from datetime import datetime
        from pathlib import Path

        agent = JamieAgent()

        # Create logger directly
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)

        logger = logging.getLogger("jamie_tests")
        logger.setLevel(logging.INFO)

        # Create file handler with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"jamie_test_results_{timestamp}.log"
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.INFO)

        # Create formatter
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(formatter)

        # Add handler to logger
        logger.addHandler(file_handler)

        print("✅ Agent initialized successfully")
        print("📝 Logger set up - results will be saved to logs/ directory")
        print("\n🚀 Running comprehensive test suite...")
        print("   - 10 Restaurant conversation tests")
        print("   - 10 Recipe conversation tests")
        print("   - Including 2 long 10-turn conversations")
        print("   - Performance timing for each turn")
        print("\n" + "=" * 50)

        # Run all tests
        results = test_instance.run_all_tests(agent, logger)

        print("\n" + "=" * 50)
        print("🎉 Test Suite Completed Successfully!")
        print(f"📊 Total tests run: {len(results)}")

        # Calculate summary stats
        total_time = sum(r["total_time"] for r in results)
        avg_time = total_time / len(results) if results else 0

        print(f"⏱️  Total execution time: {total_time:.2f} seconds")
        print(f"📈 Average test time: {avg_time:.2f} seconds")

        # Count turns
        total_turns = sum(len(r["conversation"]) for r in results)
        print(f"💬 Total conversation turns: {total_turns}")

        print(f"\n📋 Detailed results saved to logs directory")
        print("🔍 Review the log files to see how the agent performed!")

    except Exception as e:
        print(f"❌ Error running tests: {e}")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
