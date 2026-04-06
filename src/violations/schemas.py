from pydantic import BaseModel, ConfigDict


class ViolationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    