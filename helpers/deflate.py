import base64
import zlib


def deflate_text(text: str) -> str:
    compressed = zlib.compress(text.encode("utf-8"), level=9)
    return base64.b64encode(compressed).decode("ascii")


def inflate_text(encoded: str) -> str:
    compressed = base64.b64decode(encoded)
    return zlib.decompress(compressed).decode("utf-8")