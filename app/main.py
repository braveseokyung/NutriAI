from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy.inspection import inspect
from typing import List, Dict, Optional
import uuid
import json
from .schemas import NutrientSchema, RESPONSE_1, RESPONSE_2,RESPONSE_3, UserInput
from .models import Nutrient
from openai import OpenAI
from sqlalchemy import text
from sqlalchemy import func, any_
from supabase import Client, create_client

from . import models
from app.database import SessionLocal, engine

from dotenv import load_dotenv
import os

# .env 파일 활성화
load_dotenv()

API_KEY = os.getenv('API_KEY')
SUP_API_URL=os.getenv('SUP_API_URL')
SUP_API_KEY=os.getenv('SUP_API_KEY')

CHAT_MODEL="gpt-4o-2024-08-06"

supabase_client: Client = create_client(SUP_API_URL, SUP_API_KEY)

models.Base.metadata.create_all(bind=engine)

app = FastAPI()


@app.get("/get_db")
def get_db():
    db = SessionLocal()
    
    try:
        yield db
    finally:
        db.close()


# Nutrient 테이블의 모든 데이터를 반환하는 함수
@app.get("/data", response_model=List[NutrientSchema])  # Adjust response_model to match your pydantic model
def get_all_data(db: Session = Depends(get_db)):
    data = db.query(Nutrient).all()
    return data

# nutrient 정보를 dictionary로 반환 (아래 category 함수의 형식 지정에 필요)
def nutrient_to_dict(nutrient):
    return {
        "NUT_NM": nutrient.NUT_NM,
        "NUT_FNCLTY": nutrient.NUT_FNCLTY,
        "PRDCT_LINK": nutrient.PRDCT_LINK,
        "MJR_CATEGORY": nutrient.MJR_CATEGORY,
        "PRDCT_TITLE": nutrient.PRDCT_TITLE,
        "PRDCT_IMG": nutrient.PRDCT_IMG,
        "PRDCT_PRICE": nutrient.PRDCT_PRICE
    }

# Nutrient 테이블에서 category에 해당하는 데이터를 return
@app.get("/category/{category}")
def get_data_by_category(category: str):
    # MJR_CATEGORY 배열에서 category 값이 포함된 행을 필터링
    db=SessionLocal()
    results = db.query(Nutrient).filter(
        category == any_(Nutrient.MJR_CATEGORY)  # any_() 사용
    ).all()
    db.close()

    nutrient_list = [nutrient_to_dict(nutrient) for nutrient in results]
    
    return str(nutrient_list)


# conversation : 가장 메인, 여기서 모든 llm 모델을 사용해서 응답을 return
@app.post("/conversation")
def conversation(user_prompt: UserInput , nickname : str, conversation_id: Optional[str] = Query(None)):
    # conversation id를 입력하지 않거나 conversation table에 id가 없으면
    if conversation_id is None or supabase_client.table("conversation").select("*").eq("id", conversation_id) is None:
        # 새로운 대화 시작 (대화 id 생성)
        conversation_id = str(uuid.uuid4())
        conversation = list()

        # 시스템 메시지 추가
        conversation_system = {
            "role": "system",
            "content": "You are a health assistant. Call the user {nickname}. You should simply ask the user about their symptoms so that you can narrow their symptoms. If user input needs more specifying, return {1} along with your response. Else, if user input is specified enough, answer {2} and finish conversation. You should answer in Korean."
        }

        conversation.append(conversation_system)
       
        # 새로운 conversation conversation DB에 추가
        supabase_client.table("conversation").insert({
            "id": conversation_id,
            "nickname": nickname,
            "conversation": conversation
        }).execute()
        
    else:
        
        # DB에서 기존 conversation conversation id를 가지고 불러오기
        res = supabase_client.table("conversation").select("*").eq("id", conversation_id).execute()
        conversation = res.data[0]['conversation']

    # 사용자 메시지 추가
    conversation.append(dict({"role": "user", "content": user_prompt.message}))

    # 대화 처리 및 응답 생성
    user_input_type, answer = chatbot_ask_symptom(conversation)

    # 어시스턴트 응답 추가
    conversation.append({"role": "assistant", "content": answer})

    # 대화 상태 업데이트
    supabase_client.table("conversation").update({
        "conversation": conversation
    }).eq("id", conversation_id).execute()

    # 대화 종료 여부 확인
    if user_input_type == 2:
        symptom, category = summarize_and_categorize(conversation)

        data_category=get_data_by_category(category)
        symptom,info_nut_nm, info_nut_fnclty,info_prdct_title,info_prdct_link,info_prdct_image,info_prdct_price=compare_and_recommend(symptom,data_category)
        
        # 대화 종료: 디비 conversation 테이블에서 제거
        supabase_client.table("conversation").delete().eq("id", conversation_id).execute()
        
        return {
            "symptom": symptom,
            "info_nut_nm": info_nut_nm,
            "info_nut_fnclty":info_nut_fnclty,
            "info_prdct_title":info_prdct_title,
            "info_prdct_link":info_prdct_link,
            "info_prdct_image":info_prdct_image,
            "info_prdct_price":info_prdct_price
        }

    # user_input_type=1(대화를 지속해야 하는 경우)
    # conversation_id, user_input_type, response를 return
    return {
        "conversation_id": conversation_id,
        "user_input_type":user_input_type,
        "response": answer
    }

# LLM 1 : 증상을 물어보는 LLM
@app.get("/chat")
def chatbot_ask_symptom(conversation):

    client=OpenAI(api_key=API_KEY)

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

    # 지속여부(1,2)와 응답을 return
    return user_input_type, answer


# LLM 2 : 증상을 요약하고 카테고리로 분류하는 함수
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
    json_response=json.loads(response)
    symptom=json_response['SYMPTOM']
    category=json_response['CATEGORY']

    # 최종 증상과 카테고리(대분류) 반환
    return symptom, category   

# LLM 3: 카테고리에 해당하는 모든 데이터의 증상을 최종 증상과 비교해서 가장 적합한 영양제 정보를 가져오는 함수
@app.get("/recommend")
def compare_and_recommend(symptom, data_category):

    conversation_recommendation=[]
    llm_3_role={"role": "system", "content":f"The user's symptom is {symptom}. The following is the information of nutrient product that might help such symptom. products:{data_category}. Comparing 'NUT_FNCLTY' of each product, choose 1 that is most suitable for the symptom. For the answer, describe user's symptom and show information of nutrient in organized form. Answer in Korean"}
    conversation_recommendation.append(llm_3_role)

    client=OpenAI(api_key=API_KEY)
    CHAT_MODEL="gpt-4o-2024-08-06"
  
    response = client.beta.chat.completions.parse(
        model=CHAT_MODEL,
        messages=conversation_recommendation,
        response_format=RESPONSE_3
    )

    response=response.choices[0].message.content
    json_response=json.loads(response)
    symptom_answer=json_response['SYMPTOM']
    info_nut_nm=json_response['INFO_NUT_NM']
    info_nut_fnclty=json_response['INFO_NUT_FNCLTY']
    info_prdct_title=json_response['INFO_PRDCT_TITLE']
    info_prdct_link=json_response['INFO_PRDCT_LINK']
    info_prdct_image=json_response['INFO_PRDCT_IMAGE']
    info_prdct_price=json_response['INFO_PRDCT_PRICE']

    # 최종 증상 요약 한 줄과 영양제 관련 정보를 출력
    return symptom_answer, info_nut_nm, info_nut_fnclty, info_prdct_title, info_prdct_link, info_prdct_image, info_prdct_price


@app.get("/")
def hello():
    return {"Hello": "World"}