from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.inspection import inspect
from typing import List, Dict
import uuid
import json
from .schemas import NutrientSchema, RESPONSE_1, RESPONSE_2, UserInput
from .models import Nutrient
from openai import OpenAI
from sqlalchemy import text
from sqlalchemy import func, any_

from . import models
from app.database import SessionLocal, engine

from dotenv import load_dotenv
import os

# .env 파일 활성화
load_dotenv()

API_KEY = os.getenv('API_KEY')
CHAT_MODEL="gpt-4o-2024-08-06"

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

@app.get("/category/{category}")
def get_data_by_category(category: str, db: Session = Depends(get_db)):
    # MJR_CATEGORY 배열에서 category 값이 포함된 행을 필터링
    results = db.query(Nutrient).filter(
        category == any_(Nutrient.MJR_CATEGORY)  # any_() 사용
    ).all()
    
    return results

# 대화 상태를 저장하는 딕셔너리 (실제 운영 환경에서는 데이터베이스 사용 권장)
conversations: Dict[str, List[Dict[str, str]]] = {}

@app.post("/conversation/{conversation_id}")
def conversation(user_prompt: UserInput, conversation_id: str = None):
    if conversation_id is None or conversation_id not in conversations:
        # 새로운 대화 시작
        conversation_id = str(uuid.uuid4())
        conversation = []

        # 시스템 메시지 추가
        conversation_system = {
            "role": "system",
            "content": "You are a health assistant. You should simply ask the user about their symptoms so that you can narrow their symptoms. If user input needs more specifying, return {1} along with your response. Else, if user input is specified enough, answer {2} and finish conversation. You should answer in Korean."
        }
        conversation.append(conversation_system)
    else:
        # 기존 대화 이어나가기
        conversation = conversations[conversation_id]

    # 사용자 메시지 추가
    conversation.append({"role": "user", "content": user_prompt.message})

    # 대화 처리 및 응답 생성
    user_input_type, answer = chatbot_ask_symptom(user_prompt.message, conversation_id)

    # 어시스턴트 응답 추가
    # conversation.append({"role": "assistant", "content": answer})

    # 대화 상태 저장
    conversations[conversation_id] = conversation

    # 대화 종료 여부 확인
    if user_input_type == 2:
        symptom, category = summarize_and_categorize(conversation_id)
        
        # 대화 종료: 상태에서 제거
        del conversations[conversation_id]
        
        data_category=get_data_by_category(category)
        symptom,info=compare_and_recommend(symptom,data_category)

        return {
            "symptom": symptom,
            "info": info
        }


    return {
        "conversation_id": conversation_id,
        "user_input_type":user_input_type,
        "response": answer
    }


@app.get("/chat")
def chatbot_ask_symptom(user_prompt, conversation_id):

    client=OpenAI(api_key=API_KEY)
    conversation=conversations[conversation_id]

    conversation.append({"role": "user", "content": user_prompt})

    response = client.beta.chat.completions.parse(
        model=CHAT_MODEL,
        messages=conversation,
        response_format=RESPONSE_1
    )

    response_content = response.choices[0].message.content
    
    try:
        json_response = json.loads(response_content)
        user_input_type = json_response['TYPE']
        answer = json_response['ANSWER']
    except json.JSONDecodeError:
        user_input_type = 2  # 기본값으로 종료
        answer = response_content

    return user_input_type, answer


@app.get("/summarize")
def summarize_and_categorize(conversation_id):

    CATEGORIES=['인지기능/기억력', '긴장', '수면의 질', '피로', '치아', '눈', '피부', '간', '위', '장', '체지방', '칼슘흡수', '혈당', '갱년기 여성', '갱년기 남성', '월경 전 불편한 상태', '혈중 중성지방', '콜레스테롤', '혈압', '혈행', '면역', '항산화', '관절', '뼈', '근력', '운동수행능력', '전립선', '배뇨', '요로']
    llm_2_role={"role": "system", "content":f"Summarize the symptoms in one line. Also categorize the symptom. The category must belong in {', '.join(CATEGORIES)}"}
    conversation=conversations[conversation_id]
    
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

# category -> db에서 카테고리에 해당하는 로우를 다 가져옴

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


@app.get("/")
def hello():
    return {"Hello": "World"}