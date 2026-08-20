# This package redirects imports to the backend src directory
import os
import sys

# Determine the path to the backend src directory relative to this file (one level up)
_current_dir = os.path.dirname(__file__)
_backend_src = os.path.abspath(os.path.join(_current_dir, "..", "backend", "src"))
# Extend the package __path__ so submodules are found in backend/src
if _backend_src not in __path__:
    __path__.append(_backend_src)
