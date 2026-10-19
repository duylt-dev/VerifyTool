"""MO workbook reader (static-check-spec §3)."""

import unicodedata
from pathlib import Path

import openpyxl

from apkverify.errors import SpecError
from apkverify.model import Placement, Spec


def _text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _header(value: object) -> str:
    return unicodedata.normalize("NFC", str(value)).strip().casefold()


def read_spec(path: Path) -> Spec:
    try:
        workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
        try:
            sheet = workbook.worksheets[0]
            columns = None
            title = group = group_note = ""
            placements = []
            required = {_header(h) for h in ("Định Dạng", "Config Name", "Ad Space", "ID")}
            for number, values in enumerate(sheet.iter_rows(min_row=1, values_only=True), 1):
                if columns is None:
                    if number > 20:
                        break
                    headers = {_header(v): i for i, v in enumerate(values)}
                    if required <= headers.keys():
                        columns = headers
                    elif not title:
                        title = next((_text(v) for v in values if _text(v)), "")
                    continue

                cells = {name: _text(values[index]) for name, index in columns.items() if index < len(values)}

                def cell(name: str, row_cells: dict[str, str] = cells) -> str:
                    return row_cells.get(_header(name), "")

                if cell("STT"):
                    group, group_note = cell("Task"), cell("Ghi chú AD")
                if cell("Định Dạng"):
                    placements.append(
                        Placement(
                            number,
                            group,
                            group_note,
                            cell("Task"),
                            cell("Trạng thái"),
                            cell("Định Dạng"),
                            cell("Config Name"),
                            cell("Ad Space"),
                            cell("Network Ad Name"),
                            cell("ID"),
                            cell("Ghi chú AD"),
                            cell("Mã task"),
                            cell("Link ClickUp"),
                        )
                    )
            if columns is None:
                raise SpecError(
                    f"Không tìm thấy dòng tiêu đề trong 20 dòng đầu của {path.name} "
                    "(cần các cột: Định Dạng, Config Name, Ad Space, ID)."
                )
            return Spec(path.name, sheet.title, title, tuple(placements))
        finally:
            workbook.close()
    except SpecError:
        raise
    except Exception as error:
        raise SpecError(f"Không đọc được file spec {path.name}: {error}.") from error
