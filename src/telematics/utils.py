def mask_imei(value: str | None) -> str | None:
    """
    Masks an IMEI string using '*'.
    Masks all characters except the last 4 digits.
    Example: '864239040123456' -> '***********3456'.
    """
    if value is None:
        return None

    value = value.strip()
    if not value:
        return value

    length = len(value)
    if length <= 4:
        return "*" * length

    return "*" * (length - 4) + value[-4:]
