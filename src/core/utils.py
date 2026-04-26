import re


def to_lower_camel_case(value: str, max_length: int | None = None) -> str:
    """
    Convert a string to lowerCamelCase.

    Examples:
        TV Show Page -> tvShowPage
        Discover Page -> discoverPage
        My API Endpoint -> myApiEndpoint
    """
    words = re.findall(r"[0-9A-Za-z]+", value or "")

    if not words:
        return ""

    result = words[0].lower() + "".join(word.capitalize() for word in words[1:])

    if max_length:
        result = result[:max_length]

    return result
