from pydantic import BaseModel

class CourseRequest(BaseModel):
    topic: str
    target_audience: str
    estimated_modules: int
    additional_info: str | None = None