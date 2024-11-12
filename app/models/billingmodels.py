from pydantic import BaseModel
from enum import Enum

class CarrierEnum(str, Enum):
    FEDEX = "FEDEX"
    fedex = "FEDEX"
    UPS = "UPS"
    ups = "UPS"

class Credentials(BaseModel):
    username: str
    password: str
    carrier: CarrierEnum
