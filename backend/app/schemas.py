from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ImagePayload(BaseModel):
    name: str = "image"
    dataUrl: str = Field(..., description="data:image/...;base64,... 형태의 data URL")


class AnalyzeOptions(BaseModel):
    zoneMode: str = "VP"
    storeType: str = "UNKNOWN"
    tone: str = "SOFT_CRITICAL"
    criteria: List[str] = Field(default_factory=list)
    focusKeywords: List[str] = Field(default_factory=list)
    extraCriteria: str = ""
    modelName: Optional[str] = None
    temperature: Optional[float] = None
    maxTokens: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class AnalyzeRequest(BaseModel):
    images: List[ImagePayload] = Field(default_factory=list)
    options: AnalyzeOptions = Field(default_factory=AnalyzeOptions)


class BatchAnalyzeRequest(AnalyzeRequest):
    pass


class ConsumerPhotoRequest(BaseModel):
    image: ImagePayload


class ConsumerAskRequest(BaseModel):
    question: str = Field(..., min_length=1)


class ConsumerCatalogRequest(BaseModel):
    item_type: str = Field(..., min_length=1)
