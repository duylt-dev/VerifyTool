"""Errors the user can act on (best-practices §7). Messages are Vietnamese and printed without a traceback.

A finding (missing ID, config off, ...) is never an exception: it is a `model.Finding`. Exceptions mean the check
could not run at all.
"""


class VerifyError(Exception):
    """Base class; `cli` maps it to exit code 2."""


class InputError(VerifyError):
    """Input files missing, ambiguous or unreadable."""


class SpecError(VerifyError):
    """The spec workbook cannot be read as MO's layout."""


class ApkError(VerifyError):
    """The APK cannot be opened or parsed."""


class AdbError(VerifyError):
    """adb missing, no usable device, or an adb command failed."""


class RcFormatError(ValueError):
    """A Remote Config value is not JSON of the expected shape.

    Not a VerifyError: `checks/rc_checks.py` turns it into the finding RC-JSON-INVALID.
    """
