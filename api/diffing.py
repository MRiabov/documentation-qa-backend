import difflib


def unified_diff(
    old: str, new: str, fromfile: str = "doc_before.md", tofile: str = "doc_after.md"
) -> str:
    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    diff = difflib.unified_diff(old_lines, new_lines, fromfile=fromfile, tofile=tofile)
    return "".join(diff)
