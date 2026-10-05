import os
import sys
import pytest

if __name__ == "__main__":
    os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    args = sys.argv[1:] if len(sys.argv) > 1 else ["tests"]
    sys.exit(pytest.main(args))
