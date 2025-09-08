from textwrap import dedent
from typing import List, Optional, Dict, Any
import json


def build_prompt(
    doc: str,
    feedback: str | None = None,
    *,
    allow_code_edits: bool = False,
    lint_issues: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """
    Build the instruction prompt. We rely on STOP sequences ("</json>")
    so the model should stream only the JSON and stop before the closing tag.
    """
    base = [
        "You are a precise documentation quality reviewer for software engineers.",
        "Input is a Markdown document. Identify writing issues and suggest concise fixes.",
        "",
    ]

    if allow_code_edits:
        code_policy = [
            "You MAY propose changes inside fenced code blocks (``` … ```):",
            "- Keep code correct; prefer minimal, surgical edits.",
            "- Add concise, self-explanatory comments where helpful.",
            "- If the fence lacks a language label, propose one (e.g., ```py).",
            "- Fix obvious formatting issues (indentation, spacing, line breaks).",
        ]
    else:
        code_policy = [
            "DO NOT propose changes inside fenced code blocks (``` … ```).",
        ]

    common_policy = [
        "DO NOT propose changes inside:",
        "- inline code (`code`),",
        "- or URLs.",
        "",
        "When proposing replacements, keep surrounding Markdown intact.",
        "Also improve Markdown structure when helpful: headings, bold/italic emphasis, lists, and code-fence language labels.",
        "",
        "Return ONLY a JSON object inside <json>…</json> matching this TypeScript schema:",
        "",
        'type Severity = "info" | "warning" | "error";',
        "type Issue = {",
        "  id: string;",
        "  rule: string;",
        "  message: string;",
        "  severity: Severity;",
        "  replace_text: string;",
        "  replace_with: string;",
        "  replacement?: string;",
        "  replacements?: { label: string; text: string }[];",
        "};",
        "type ReviewResponse = { version: string; issues: Issue[] };",
        "",
        "Guidelines:",
        "- Prefer clear and direct wording over hedging (e.g., very, just, simply, actually, obviously, clearly).",
        "- Prefer simple words (e.g., 'use' over 'utilize').",
        "- Avoid fluff/filler.",
        "- Optional: grammar/clarity fixes when safe.",
        "- Be conservative; avoid risky rewrites.",
    ]

    prelude = dedent("\n".join(base + code_policy + common_policy)).strip()

    regen = ""
    if feedback:
        regen = dedent(
            f"""
            
            The previous attempt was malformed and could not be applied.
            Reason: {feedback}

            Regenerate and return ONLY a valid JSON object within <json>…</json> that follows the schema exactly.
            Ensure for each issue that:
            - replace_text matches exactly one occurrence outside fenced code blocks, inline code, and URLs;
            - replace_with is provided;
            - do not include any extra commentary outside <json>…</json>.
            """
        ).strip()

    lint_block = ""
    if lint_issues:
        lint_json = json.dumps(lint_issues, ensure_ascii=False)
        lint_block = dedent(
            f"""
            
            <lint>
            {lint_json}
            </lint>
            
            Do NOT duplicate issues already present in <lint>. Prefer to complement them with structural and clarity improvements.
            """
        ).strip()

    open_doc = """
        <doc>
    """.strip()

    closing = """
        </doc>

        <json>
    """.strip()

    # We intentionally do not include </json> here; TGI stop sequence will stop generation before it.
    return f"{prelude}\n{regen}\n{lint_block}\n{open_doc}\n{doc}\n{closing}\n"
