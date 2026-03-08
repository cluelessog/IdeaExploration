from __future__ import annotations
import json
import logging
from pathlib import Path
from ideagen.core.models import RunResult, IdeaReport

logger = logging.getLogger("ideagen")


def export_run(result: RunResult, output_dir: str = "./ideagen_output") -> Path:
    """Export a RunResult to a pretty-printed JSON file."""
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    timestamp = result.timestamp.strftime("%Y%m%d_%H%M%S")
    filename = f"ideagen_run_{timestamp}.json"
    file_path = out_path / filename

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
