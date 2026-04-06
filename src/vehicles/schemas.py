from pydantic import BaseModel, ConfigDict, field_serializer


def _mask_owner_name(value: str | None) -> str | None:
    if value is None:
        return None

    value = value.strip()
    if not value:
        return None

    parts = value.split()
    masked_parts = []
    for part in parts:
        if len(part) <= 2:
            masked_parts.append(part[0] + "*" if len(part) == 2 else "*")
            continue

        masked_parts.append(part[0] + "*" * (len(part) - 2) + part[-1])

    return " ".join(masked_parts)


class VehicleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    vehicle_number: str
    category: str | None = None
    category_description: str | None = None
    maker_description: str | None = None
    maker_model: str | None = None
    body_type: str | None = None
    fuel_type: str | None = None
    color: str | None = None
    manufacturing_date: str | None = None
    cubic_capacity: float | None = None
    owner_name: str | None = None
    rto_code: str | None = None

    @field_serializer("owner_name")
    def serialize_owner_name(self, value: str | None):
        return _mask_owner_name(value)