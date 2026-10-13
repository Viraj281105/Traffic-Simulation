"""Spreadsheet-safe text for CSV exports.

A CSV cell that begins with ``=``, ``+``, ``-``, ``@`` (or a tab / carriage
return) is evaluated as a formula by Excel, LibreOffice and Google Sheets.
Exports carry user-entered text (run names, notes, tags, suite and study
titles), so such a cell is prefixed with an apostrophe, which spreadsheets
display as plain text (OWASP "CSV injection").

Only text is changed: a string that is a plain number (``-3.5``) is data, not
a formula, and is left exactly as it is, so numeric columns stay numeric.
"""

from __future__ import annotations

_TRIGGERS = ("=", "+", "-", "@", "\t", "\r")


def spreadsheet_safe(text: str) -> str:
    if not text or not text.startswith(_TRIGGERS):
        return text
    try:
        float(text)
    except ValueError:
        return "'" + text
    return text
