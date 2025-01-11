import pytest
import sys
from pathlib import Path

# Add parent directory to Python path for all tests
sys.path.append(str(Path(__file__).parent.parent))

@pytest.fixture(autouse=True)
def setup_test_env():
    """Setup test environment for all tests."""
    # You can add any common setup code here
    yield
    # You can add any common cleanup code here 