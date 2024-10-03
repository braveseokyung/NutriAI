# pydantic

from pydantic import BaseModel 
from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, VARCHAR, TEXT, ARRAY
from sqlalchemy.orm import relationship

from app.database import Base

class Nutrient(Base):
    __tablename__="main_final"
    id = Column(Integer, primary_key=True, index=True)
    NUT_NM = Column(TEXT, unique=False, index=False)
    NUT_FNCLTY = Column(TEXT, unique=False, index=False)
    PRDCT_TITLE = Column(VARCHAR, unique=False, index=False)
    PRDCT_LINK = Column(TEXT, unique=False, index=False)
    PRDCT_IMG = Column(TEXT, unique=False, index=False)
    PRDCT_PRICE = Column(TEXT, unique=False, index=False)
    MJR_CATEGORY = Column(ARRAY(String), unique=False, index=False)

