"""
Source registry.

To add a new rain-forecast source:

1. Create ``sources/<your_source>/`` containing ``client.py``, ``parser.py``,
   ``const.py``, ``errors.py``, and an ``__init__.py`` exporting a
   module-level :class:`Source` instance named ``SOURCE``.
2. Append it to :data:`SOURCES` below.
3. Add a matching entry under ``entity.sensor`` in the
   ``translations/*.json`` files for the new ``entity_key``.

The coordinator, sensor platform, and config flow will pick it up
automatically.
"""

from __future__ import annotations

from ._base import Source, SourceClient
from .buienalarm import SOURCE as BUIENALARM
from .buienradar import SOURCE as BUIENRADAR
from .open_meteo import SOURCE as OPEN_METEO

SOURCES: tuple[Source, ...] = (BUIENRADAR, BUIENALARM, OPEN_METEO)

__all__ = [
    "BUIENALARM",
    "BUIENRADAR",
    "OPEN_METEO",
    "SOURCES",
    "Source",
    "SourceClient",
]
