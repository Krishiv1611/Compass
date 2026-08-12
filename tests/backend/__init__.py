"""Backend-specific tests that coexist with Compass's namespace package."""

from pkgutil import extend_path

# ``unittest discover -s tests`` imports this directory as ``backend``. Extend
# that package path so application imports such as ``backend.routers`` continue
# to resolve from the repository's namespace-package directory.
__path__ = extend_path(__path__, __name__)
