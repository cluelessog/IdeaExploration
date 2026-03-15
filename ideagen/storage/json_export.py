from __future__ import annotations
import json
import logging
from pathlib import Path
from ideagen.core.models import RunResult, IdeaReport

logger = logging.getLogger("ideagen")


def export_run(
    result: RunResult,
    output_dir: str = "./ideagen_output",
    output_path: Path | None = None,
) -> Path:
    """Export a RunResult to a pretty-printed JSON file.

    If *output_path* is provided and has a file suffix (e.g. ``.json``), the
    result is written to that exact path.  If *output_path* has no suffix it is
    treated as a directory and a timestamped filename is generated inside it.
    When *output_path* is ``None`` the legacy *output_dir* behaviour is used.
    """
    if output_path is not None:
        p = Path(output_path)
        if p.suffix:
            # Treat as an exact target file.
            file_path = p
        else:
            # Treat as a directory — generate a timestamped name inside it.
            timestamp = result.timestamp.strftime("%Y%m%d_%H%M%S")
            file_path = p / f"ideagen_run_{timestamp}.json"
    else:
        out_path = Path(output_dir)
        timestamp = result.timestamp.strftime("%Y%m%d_%H%M%S")
        file_path = out_path / f"ideagen_run_{timestamp}.json"

    file_path.parent.mkdir(parents=True, exist_ok=True)

    data = json.loads(result.model_dump_json())
    file_path.write_text(json.dumps(data, indent=2, default=str))

    logger.info(f"Exported run to {file_path}")
    return file_path


def export_idea(report: IdeaReport, output_dir: str = "./ideagen_output") -> Path:
    """Export a single IdeaReport to a JSON file."""
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    safe_title = "".join(c if c.isalnum() or c in "-_ " else "" for c in report.idea.title)[:50].strip()
    filename = f"idea_{safe_title.replace(' ', '_')}.json"
    file_path = out_path / filename

    data = json.loads(report.model_dump_json())
    file_path.write_text(json.dumps(data, indent=2, default=str))

    logger.info(f"Exported idea to {file_path}")
    return file_path
