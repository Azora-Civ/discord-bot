import re

def parse_list(value: str) -> list[str]:
    """
    Accepts names separated by spaces or commas.

    Example:
        Azora AzoraFarms, AzoraBuild
    """
    return [
        name
        for name in re.split(r"[\s,]+", value.strip())
        if name
    ]