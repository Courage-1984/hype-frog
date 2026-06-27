from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PipelineContext:
    sitemap_meta: dict[str, dict[str, Any]] = field(default_factory=dict)
    source_label: str = "manual_input"
