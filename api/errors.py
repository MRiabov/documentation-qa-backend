class MalformedToolCall(Exception):
    """Raised when the model output cannot be deterministically applied.

    Examples: no <json> block, invalid schema, replacement not found or ambiguous,
    replacement inside forbidden region, or overlapping edits.
    """

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason
