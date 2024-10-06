# database
from pydantic import BaseModel
from typing import List
from uuid import UUID


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
        from_attributes = True 

class ConversationSchema(BaseModel):
    user_id : UUID
    nickname : str
    conversation: List[str]

    class Config:
        arbitrary_types_allowed=True

class RESPONSE_1(BaseModel):
    TYPE:int
    ANSWER:str

class RESPONSE_2(BaseModel):
    SYMPTOM:str
    CATEGORY:str

class RESPONSE_3(BaseModel):
    SYMPTOM:str
    INFO_NUT_NM:str
    INFO_NUT_FNCLTY:str
    INFO_PRDCT_TITLE:str
    INFO_PRDCT_LINK:str
    INFO_PRDCT_IMAGE:str
    INFO_PRDCT_PRICE:int

class UserInput(BaseModel):
    message: str
