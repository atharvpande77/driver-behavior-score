from pydantic import BaseModel, ConfigDict, field_serializer

from src.vehicles.utils import mask_owner_name


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
        return mask_owner_name(value)