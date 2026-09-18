"""Sanity check: the package installs and imports correctly."""

import datasonde


def test_package_has_version() -> None:
    assert isinstance(datasonde.__version__, str)
    assert datasonde.__version__ != ""