from datetime import datetime, timezone


def timestamp(value: str | None) -> str:
    if value is None:
        return "Unknown"

    dt = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    dt = dt.replace(tzinfo=timezone.utc)

    return f"<t:{int(dt.timestamp())}:F>"
