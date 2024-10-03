from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session
from typing import List
from .schemas import NutrientSchema
from .models import Nutrient

from . import models, schemas
from app.database import SessionLocal, engine

models.Base.metadata.create_all(bind=engine)

app = FastAPI()


@app.get("/get_db")
def get_db():
    db = SessionLocal()
    
    try:
        yield db
    finally:
        db.close()

@app.get("/data", response_model=List[NutrientSchema])  # Adjust response_model to match your pydantic model
def get_all_data(db: Session = Depends(get_db)):
    data = db.query(Nutrient).all()
    return data


@app.get("/")
def hello():
    return {"Hello": "World"}