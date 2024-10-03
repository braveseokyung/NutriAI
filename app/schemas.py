# database
from pydantic import BaseModel
from typing import List


class NutrientSchema(BaseModel):
    id: int
    NUT_NM: str
    NUT_FNCLTY: str
    PRDCT_TITLE: str
    PRDCT_LINK: str
    PRDCT_IMG: str
    PRDCT_PRICE: int
    MJR_CATEGORY: List[str]  # ARRAY 필드이므로 List로 설정

    class Config:
        orm_mode = True 

