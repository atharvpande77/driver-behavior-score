def mask_owner_name(value: str | None) -> str | None:
    if value is None:
        return None

    value = value.strip()
    if not value:
        return None

    parts = value.split()
    masked_parts: list[str] = []
    for part in parts:
        if len(part) <= 2:
            masked_parts.append(part[0] + "*" if len(part) == 2 else "*")
            continue

        masked_parts.append(part[0] + "*" * (len(part) - 2) + part[-1])

    return " ".join(masked_parts)
