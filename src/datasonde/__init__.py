"""DataSonda: automated data profiling, quality assessment and exploratory analysis.

The public API (``analyze`` and ``Report``) is provisional while the version is
``0.1.0.dev0``.
"""

from datasonde._version import __version__
from datasonde.report import Report, analyze

__all__ = ["Report", "__version__", "analyze"]
