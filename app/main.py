from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session
from typing import List
import json
from .schemas import NutrientSchema, RESPONSE_1, RESPONSE_2
from .models import Nutrient
from openai import OpenAI


from . import models, schemas
from app.database import SessionLocal, engine

from dotenv import load_dotenv
import os

# .env 파일 활성화
load_dotenv()

API_KEY = os.getenv('API_KEY')

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

# 처음에 conversation 정의가 필요
# conversation=[]
# llm_1_role={"role": "system", "content":"You are a health assistant. You should simply ask the user about their symptoms so that you can narrow their symptoms. If user input needs more specifying, return {1} along with your response. Else, if user input is specified enough, answer {2} and finish conversation.You should answer in Korean"}
# conversation.append(llm_1_role)

# 1이 return 될 때는 계속, 2가 return 되면 stop
@app.get("/chat")
def chatbot_ask_symptom(prompt, conversation):

    conversation.append({"role": "user", "content": prompt})

    client=OpenAI(api_key=API_KEY)
    CHAT_MODEL="gpt-4o-2024-08-06"
    
    response = client.beta.chat.completions.parse(
        model=CHAT_MODEL,
        messages=conversation,
        response_format=RESPONSE_1
    )
    
    response=response.choices[0].message.content
    json_response=json.loads(response)
    user_input_type=json_response['TYPE']
    answer=json_response['ANSWER']

    return user_input_type,answer

@app.get("/summarize")
def summarize_and_categorize(conversation):

    CATEGORIES=['인지기능/기억력', '긴장', '수면의 질', '피로', '치아', '눈', '피부', '간', '위', '장', '체지방', '칼슘흡수', '혈당', '갱년기 여성', '갱년기 남성', '월경 전 불편한 상태', '혈중 중성지방', '콜레스테롤', '혈압', '혈행', '면역', '항산화', '관절', '뼈', '근력', '운동수행능력', '전립선', '배뇨', '요로']
    llm_2_role={"role": "system", "content":f"Summarize the symptoms in one line. Also categorize the symptom. The category must belong in {', '.join(CATEGORIES)}"}
    conversation.append(llm_2_role)
    
    client=OpenAI(api_key=API_KEY)
    CHAT_MODEL="gpt-4o-2024-08-06"
    
    response = client.beta.chat.completions.parse(
        model=CHAT_MODEL,
        messages=conversation,
        response_format=RESPONSE_2
    )

    response=response.choices[0].message.content
    # print(response)
    json_response=json.loads(response)
    symptom=json_response['SYMPTOM']
    category=json_response['CATEGORY']

    return symptom, category   

@app.get("/recommend")
def compare_and_recommend(symptom, data_category):

    conversation_recommendation=[]
    llm_3_role={"role": "system", "content":f"The user's symptom is {symptom}. The following is the information of nutrient product that might help such symptom. products:{data_category}. Comparing 'NUT_FNCLTY' of each product, choose 1 that is most suitable for the symptom. For the answer, describe user's symptom and show information of nutrient in organized form. Answer in Korean"}
    conversation_recommendation.append(llm_3_role)

    client=OpenAI(api_key=API_KEY)
    CHAT_MODEL="gpt-4o-2024-08-06"
  
    response = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=conversation_recommendation,
    )

    response=response.choices[0].message.content

    return response 

# def get_category_dat

# def stop_or_continue():


# # ChatGPT API를 호출하는 함수
# def get_chatgpt_response(prompt: str) -> str:
#     completion = openai.chat.completions.create(
#         model="gpt-4o",  # 사용할 모델 이름
#         messages=[
#             {"role": "system", "content": "You are a helpful assistant."},
#             {"role": "user", "content": prompt}
#         ]
#     )
#     return completion.choices[0].message.content

# # FastAPI 라우트 - DB에서 데이터를 가져와 ChatGPT API를 호출하는 함수
# @app.get("/nutrient-info/{nutrient_id}")
# def get_nutrient_info(nutrient_id: int, db: Session = Depends(get_db)):
#     # 데이터베이스에서 Nutrient 데이터 가져오기
#     nutrient = db.query(Nutrient).filter(Nutrient.id == nutrient_id).first()

#     if nutrient is None:
#         return {"error": "Nutrient not found"}

#     # ChatGPT API에 전달할 프롬프트 작성
#     prompt = f"Tell me about the nutrient '{nutrient.NUT_NM}'. It has the following functionality: {nutrient.NUT_FNCLTY}. Also, here is a product related to it: {nutrient.PRDCT_TITLE}. What are the benefits of this nutrient?"

#     # ChatGPT API 호출
#     chatgpt_response = get_chatgpt_response(prompt)

#     # 응답 반환
#     return {
#         "nutrient": NutrientSchema.from_orm(nutrient),
#         "chatgpt_response": chatgpt_response
#     }

@app.get("/")
def hello():
    return {"Hello": "World"}