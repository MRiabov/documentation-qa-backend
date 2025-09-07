import re
from typing import List, Tuple

Span = Tuple[int, int]  # [start, end)


def _merge_spans(spans: List[Span]) -> List[Span]:
    if not spans:
        return []
    spans.sort(key=lambda x: x[0])
    merged: List[Span] = []
    cur_start, cur_end = spans[0]
    for s, e in spans[1:]:
        if s <= cur_end:  # overlap or touch
            cur_end = max(cur_end, e)
        else:
            merged.append((cur_start, cur_end))
            cur_start, cur_end = s, e
    merged.append((cur_start, cur_end))
    return merged


def fenced_code_spans(text: str) -> List[Span]:
    """Return spans for triple-backtick fenced blocks, inclusive of fence lines."""
    spans: List[Span] = []
    pos = 0
    lines = text.splitlines(keepends=True)
    inside = False
    start_pos = -1
    for line in lines:
        stripped = line.lstrip()
        if not inside:
            fence_idx = stripped.find("```")
            if fence_idx == 0:
                inside = True
                # compute absolute index of the first backtick in this line
                start_pos = pos + (len(line) - len(stripped)) + fence_idx
        else:
            fence_idx = stripped.find("```")
            if fence_idx == 0:
                # include the entire closing fence line
                end_pos = pos + len(line)
                spans.append((start_pos, end_pos))
                inside = False
                start_pos = -1
        pos += len(line)
    # if unclosed fence, treat rest of file as fenced
    if inside and start_pos != -1:
        spans.append((start_pos, len(text)))
    return _merge_spans(spans)


INLINE_CODE_RE = re.compile(r"`+")
URL_RE = re.compile(r"https?://[^\s<>)\]}\"]+")
MD_LINK_URL_RE = re.compile(r"\]\((https?://[^)]+)\)")
AUTO_LINK_RE = re.compile(r"<https?://[^>]+>")


def inline_code_spans(text: str, blocked: List[Span]) -> List[Span]:
    """Return spans for inline code using single backticks, ignoring fenced blocks."""
    spans: List[Span] = []
    blocked_iter = iter(sorted(blocked))
    cur_block = next(blocked_iter, None)

    def in_block(i: int) -> bool:
        nonlocal cur_block
        while cur_block is not None and i >= cur_block[1]:
            cur_block = next(blocked_iter, None)
        return cur_block is not None and cur_block[0] <= i < cur_block[1]

    i = 0
    open_tick = -1
    while i < len(text):
        if in_block(i):
            i = cur_block[1] if cur_block else i + 1
            open_tick = -1
            continue
        ch = text[i]
        if ch == "`":
            if open_tick == -1:
                open_tick = i
            else:
                spans.append((open_tick, i + 1))
                open_tick = -1
        i += 1
    return _merge_spans(spans)


def url_spans(text: str) -> List[Span]:
    spans: List[Span] = []
    for m in URL_RE.finditer(text):
        spans.append((m.start(), m.end()))
    for m in MD_LINK_URL_RE.finditer(text):
        # group(1) is inside parentheses; adjust absolute positions
        url = m.group(1)
        # compute start index of URL within the whole text
        start = m.start(1)
        spans.append((start, start + len(url)))
    for m in AUTO_LINK_RE.finditer(text):
        # strip angle brackets from span
        spans.append((m.start() + 1, m.end() - 1))
    return _merge_spans(spans)


def forbidden_spans(text: str) -> List[Span]:
    fences = fenced_code_spans(text)
    inline = inline_code_spans(text, fences)
    urls = url_spans(text)
    return _merge_spans(fences + inline + urls)


def spans_intersect(a: Span, b: Span) -> bool:
    return a[0] < b[1] and b[0] < a[1]
