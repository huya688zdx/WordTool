from pydantic import BaseModel, ConfigDict


class CoordinateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    paragraph_id: str
    page_number: int
    bbox_x0: float
    bbox_y0: float
    bbox_x1: float
    bbox_y1: float
    match_confidence: float
    match_strategy: str
