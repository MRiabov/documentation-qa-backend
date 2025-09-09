import json
from api.models import ReviewResponse
from api.errors import MalformedToolCall


def extract_json_text(text: str) -> str:
    """
    Extract JSON string either from a <json>...</json> block or consider the whole text
    to be the JSON object if the tags are not present.
    """
    start_tag = "<json>"
    end_tag = "</json>"
    start = text.find(start_tag)
    end = text.rfind(end_tag)
    if start != -1:
        # If both tags are present and ordered correctly, return the enclosed content
        if end != -1 and end > start:
            return text[start + len(start_tag) : end].strip()
        # If only the opening tag is present (common when stopping on </json>),
        # return everything after the opening tag.
        return text[start + len(start_tag) :].strip()
    # Otherwise assume entire text is the JSON
    return text.strip()


def parse_review_response(text: str) -> ReviewResponse:
    json_text = extract_json_text(text)
    try:
        data = json.loads(json_text)
    except Exception as e:
        raise MalformedToolCall(
            f"Model did not return valid JSON: {e}. Model response: {json_text}"
        )
    try:
        return ReviewResponse.model_validate(data)
    except Exception as e:
        raise MalformedToolCall(
            f"JSON does not match schema: {e}. Model response: {json_text}"
        )
