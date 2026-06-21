import logging
import sys
from pathlib import Path

# Make the app module (repo root) and the build tool (tools/) importable from tests.
ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
for path in (str(ROOT), str(TOOLS)):
    if path not in sys.path:
        sys.path.insert(0, path)

# streamlit's cache_data emits a warning when used outside a running app; keep test output quiet.
logging.getLogger("streamlit.runtime.caching.cache_data_api").setLevel(logging.ERROR)
