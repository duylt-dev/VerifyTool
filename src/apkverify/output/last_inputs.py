"""Remember the answers of `apkverify project`, so the next run offers them as defaults (LLM.md §8)."""

import json
from collections.abc import Mapping
from pathlib import Path

from apkverify.output.html_report import write_file

FILE_NAME = "last-inputs.json"  # read back by input/project_reader.read_last_inputs


def write_last_inputs(out_dir: Path, answers: Mapping[str, Path]) -> Path:
    data = {key: str(path.resolve()) for key, path in answers.items()}
    return write_file(json.dumps(data, ensure_ascii=False, indent=2) + "\n", out_dir / FILE_NAME)
