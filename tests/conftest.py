import pytest
import sys
from pathlib import Path

@pytest.fixture(autouse=True)
def setup_pythonpath():
    """Add src directory to PYTHONPATH for all tests"""
    src_path = Path(__file__).parent.parent / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))