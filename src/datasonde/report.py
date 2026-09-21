"""The :class:`Report` returned by :func:`analyze`, with HTML and JSON export.

The public API of this module is provisional while the version is ``0.1.0.dev0``.
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from datasonde._version import __version__
from datasonde.html_report import render_html
from datasonde.inference import infer_types
from datasonde.models import DatasetProfile, DatasetTypeInference
from datasonde.profile import profile_dataframe

_SUPPORTED_EXTENSIONS = (".html", ".json")


@dataclass(frozen=True)
class Report:
    """The result of :func:`analyze`: a dataset profile, its type inference and a name.

    ``profile`` holds measured facts; ``inference`` holds interpretations derived from
    documented rules (it is ``None`` when the report was built without one). The API is
    provisional while the version is ``0.1.0.dev0``.
    """

    profile: DatasetProfile
    name: str | None = None
    inference: DatasetTypeInference | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-serializable form of the report.

        ``type_inference`` (with the thresholds used) is ``None`` when there is no
        inference. The format is provisional and not versioned until the dedicated JSON
        schema phase: keys may change without notice before then.
        """
        return {
            "datasonde_version": __version__,
            "dataset_name": self.name,
            "profile": self.profile.to_dict(),
            "type_inference": None if self.inference is None else self.inference.to_dict(),
        }

    def to_json(self, *, indent: int | None = 2) -> str:
        """Return the report as strict JSON (no NaN or Infinity, non-ASCII kept as is).

        The format is provisional and not versioned until the dedicated JSON schema phase.
        """
        return json.dumps(self.to_dict(), allow_nan=False, ensure_ascii=False, indent=indent)

    def to_html(self) -> str:
        """Return the report as a standalone HTML page (no script, no external resource)."""
        return render_html(
            self.profile, name=self.name, version=__version__, inference=self.inference
        )

    def export(self, path: str | os.PathLike[str]) -> Path:
        """Write the report to ``path`` and return the written :class:`~pathlib.Path`.

        The format follows the extension, case-insensitively: ``.html`` or ``.json``.
        Any other extension raises :class:`ValueError` before anything is written.
        An existing file is overwritten silently (like pandas); missing parent
        directories are not created (``FileNotFoundError``). The file is UTF-8 without
        BOM, with ``\\n`` line endings on every platform.
        """
        target = Path(path)
        extension = target.suffix.lower()
        if extension == ".html":
            content = self.to_html()
        elif extension == ".json":
            content = self.to_json()
        else:
            supported = ", ".join(_SUPPORTED_EXTENSIONS)
            raise ValueError(
                f"unsupported export extension {target.suffix!r}: use one of {supported}"
            )
        target.write_text(content, encoding="utf-8", newline="\n")
        return target


def analyze(data: Any, *, name: str | None = None) -> Report:
    """Profile a DataFrame, infer the type of each column and return a :class:`Report`.

    The type inference uses the default thresholds and no manual override. ``name`` is
    an optional dataset name shown in the report. The API is provisional while the
    version is ``0.1.0.dev0``.

    Raises:
        TypeError: ``name`` is not a ``str`` or ``None``, or ``data`` is not a DataFrame.
        ValueError: see :func:`datasonde.metadata.validate_dataframe`.
    """
    if name is not None and not isinstance(name, str):
        raise TypeError(f"name must be a str or None, got {type(name).__name__}")
    profile = profile_dataframe(data)
    return Report(profile=profile, name=name, inference=infer_types(data, profile))
