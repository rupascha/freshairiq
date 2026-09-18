"""Test bootstrap for pure FreshAirIQ logic without a Home Assistant runtime."""
from pathlib import Path
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
CUSTOM = ROOT / "custom_components"
PKG = CUSTOM / "freshairiq"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# The logic tests target modules that do not require Home Assistant. Loading
# custom_components.freshairiq normally executes integration __init__.py, which
# imports Home Assistant. Register namespace packages so these pure modules can
# be imported in a standalone CI/test environment.
if "custom_components" not in sys.modules:
    custom = types.ModuleType("custom_components")
    custom.__path__ = [str(CUSTOM)]
    sys.modules["custom_components"] = custom

if "custom_components.freshairiq" not in sys.modules:
    freshairiq = types.ModuleType("custom_components.freshairiq")
    freshairiq.__path__ = [str(PKG)]
    sys.modules["custom_components.freshairiq"] = freshairiq
