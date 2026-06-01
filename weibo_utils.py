def weibo_to_json(text: str) -> str:
    """Extract JSON from JSONP response (text between first '(' and last char - 1)."""
    begin = text.find("(")
    if begin < 0:
        return text
    end = len(text) - 1
    return text[begin + 1 : end - 1]
