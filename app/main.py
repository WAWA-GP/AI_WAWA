# app/main.py
# FastAPI 메인 서버 - AI 언어 학습 앱 (OpenAI 통합 + 데이터 수집 + Fine-tuning) with Swagger UI

# ▼▼▼ [최종 해결책] 이 코드를 파일 최상단에 추가하세요. ▼▼▼
import sys
import os

# 현재 파일(main.py)의 경로를 기준으로 프로젝트 루트 폴더(AI_WAWA)의 경로를 계산합니다.
# main.py -> app -> AI_WAWA
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Python이 모듈을 검색하는 경로 목록에 프로젝트 루트 폴더를 추가합니다.
sys.path.insert(0, project_root)
# ▲▲▲ 여기까지 추가 ▲▲▲

from dotenv import load_dotenv

load_dotenv()

import os
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Query, Path, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, Dict, List
import asyncio
from contextlib import asynccontextmanager
import json
import re
import logging
import uvicorn
from datetime import datetime, timedelta
from supabase import create_client
from app.services.pronunciation_data_service import pronunciation_data_service
from app.services.pronunciation_analysis_service import pronunciation_service
from app.services.voice_cloning_service import voice_cloning_service

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

if url and key:
    supabase = create_client(url, key)
else:
    supabase = None
    logging.warning("Supabase 설정이 없습니다.")

# 서비스 임포트
from app.services.conversation_ai_service import conversation_ai_service
from app.services.speech_recognition_service import stt_service
from app.services.text_to_speech_service import tts_service
from app.services.openai_service import openai_service
from app.services.level_test_service import level_test_service, grammar_practice_service
from app.services.voice_cloning_service import voice_cloning_service
from app.services.conversation_data_collector import data_collector
from app.services.fine_tuning_manager import fine_tuning_manager


# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 서버 시작 시 실행될 코드
    logger.info("🚀 서버 시작: 데이터셋 사전 초기화를 시작합니다...")

    # level_test_service와 grammar_practice_service의 데이터셋을 동시에 초기화
    initialization_tasks = [
        level_test_service._ensure_initialized(),
        grammar_practice_service._ensure_initialized()
    ]
    await asyncio.gather(*initialization_tasks)

    logger.info("✅ 데이터셋 사전 초기화 완료. 서버가 준비되었습니다.")

    yield

    # 서버 종료 시 실행될 코드 (현재는 비워둠)
    logger.info("🌙 서버를 종료합니다.")

class GrammarVoiceRequest(BaseModel):
    user_id: str
    audio_base64: str
    language: str
    level: str

# FastAPI 앱 생성 with Swagger 설정
app = FastAPI(
    title="AI Language Learning API with Data Collection & Fine-tuning",
    description="""
    AI 기반 언어 학습 대화 시스템 (데이터 수집 및 Fine-tuning 지원)
    
    ## 주요 기능
    * **레벨 테스트**: 적응형 언어 레벨 평가 (CEFR 표준)
    * **대화 연습**: OpenAI GPT-4 기반 실시간 대화
    * **발음 분석**: 음성 억양 및 발음 평가
    * **데이터 수집**: 모든 대화 자동 저장 및 분석
    * **Fine-tuning**: 수집된 데이터로 모델 개선
    * **개인화**: 사용자별 맞춤형 학습 경로
    
    ## 지원 언어
    한국어, 영어, 일본어, 중국어
    
    ## 데이터 수집 워크플로우
    1. 대화 세션 시작 (user_id 필수)
    2. 각 AI 응답에 대한 사용자 피드백 수집
    3. 고품질 데이터 축적 (만족도 0.7 이상)
    4. 충분한 데이터 수집 후 Fine-tuning 실행
    5. 개선된 모델로 더 나은 대화 제공
    
    ## Fine-tuning 프로세스
    - 최소 50개 고품질 대화 필요 (상황별)
    - OpenAI Fine-tuning API 사용
    - 실시간 진행 상태 모니터링
    - A/B 테스트로 성능 검증
    """,
    version="3.0.0",
    lifespan=lifespan,
    contact={
        "name": "Language Learning Team",
        "email": "support@example.com",
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT",
    },
    docs_url="/docs",
    redoc_url=None,
    openapi_url="/openapi.json"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 개발용 - 실제 배포시 특정 도메인으로 제한
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 연결된 WebSocket 클라이언트 관리
connected_clients: Dict[str, WebSocket] = {}

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """HTTP 예외를 일관된 JSON 형식으로 처리합니다."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.detail,
            "timestamp": datetime.now().isoformat()
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """처리되지 않은 모든 예외를 일관된 JSON 형식으로 처리합니다."""
    logger.error(f"예상치 못한 서버 오류 발생: {exc}")
    import traceback
    logger.error(f"상세 스택 트레이스:\n{traceback.format_exc()}")
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "요청을 처리하는 중 예기치 않은 문제가 발생했습니다. 잠시 후 다시 시도해주세요.",
            "timestamp": datetime.now().isoformat()
        }
    )

# === Pydantic 모델들 (기존 + 새로운 데이터 수집용) ===

class ConversationStartRequest(BaseModel):
    user_id: str = Field(..., description="사용자 고유 ID (데이터 수집용)")
    situation: str = Field(..., description="대화 상황 (airport, restaurant, hotel, street)")
    difficulty: str = Field("beginner", description="난이도 (beginner, intermediate, advanced)")
    language: str = Field("en", description="언어 코드 (ko, en, ja, zh)")
    mode: str = Field("auto", description="대화 모드 (scenario, openai, hybrid, auto)")
    translate: bool = False
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user_12345",
                "situation": "restaurant",
                "difficulty": "intermediate", 
                "language": "ko",
                "mode": "hybrid"
            }
        }

class TextMessageRequest(BaseModel):
    session_id: str = Field(..., description="세션 ID")
    message: str = Field(..., description="사용자 메시지")
    language: str = Field("en", description="언어 코드")
    translate: bool = Field(False, description="번역 요청 여부 (초보자 모드)") # 👈 [FIX] Add this line

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "session_12345",
                "message": "I would like to order a coffee, please.",
                "language": "en",
                "translate": True
            }
        }

class SSMLCorrectionRequest(BaseModel):
    user_id: str
    user_audio_base64: str
    target_text: str
    language: str = "en"
    user_level: str = "B1"

class VoiceMessageRequest(BaseModel):
    session_id: str = Field(..., description="세션 ID")
    audio_base64: str = Field(..., description="Base64 인코딩된 오디오 데이터")
    language: str = Field("en", description="언어 코드")
    translate: bool = Field(False, description="번역 요청 여부 (초보자 모드)") # 👈 [FIX] Add this line

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "session_12345",
                "audio_base64": "UklGRnoGAABXQVZFZm10IBAAAAABAAEA...",
                "language": "en",
                "translate": True
            }
        }

class ConversationResponse(BaseModel):
    success: bool = Field(..., description="요청 성공 여부")
    message: str = Field(..., description="응답 메시지")
    data: Optional[Dict] = Field(None, description="응답 데이터")
    error: Optional[str] = Field(None, description="오류 메시지")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "대화 세션이 시작되었습니다.",
                "data": {
                    "session_id": "session_12345",
                    "ai_message": "안녕하세요! 레스토랑 대화를 연습해봅시다.",
                    "data_collection_enabled": True
                },
                "error": None
            }
        }

# 데이터 수집용 모델들
class FeedbackRequest(BaseModel):
    session_id: str = Field(..., description="세션 ID")
    turn_index: int = Field(..., description="대화 턴 인덱스 (0부터 시작)")
    satisfaction: float = Field(..., description="만족도 (0.0-1.0)", ge=0.0, le=1.0)
    feedback_comment: Optional[str] = Field(None, description="추가 피드백 코멘트")
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "session_12345",
                "turn_index": 2,
                "satisfaction": 0.8,
                "feedback_comment": "AI 응답이 자연스럽고 도움이 되었습니다."
            }
        }

# 기존 모델들 (레벨 테스트, 발음 분석 등)
class LevelTestStartRequest(BaseModel):
    user_id: str = Field(..., description="사용자 고유 ID")
    language: str = Field("english", description="테스트 언어")
    test_type: str = Field("adaptive", description="테스트 유형 (adaptive, full, quick)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user123",
                "language": "english",
                "test_type": "adaptive"
            }
        }

class LevelTestAnswerRequest(BaseModel):
    session_id: str = Field(..., description="테스트 세션 ID")
    question_id: str = Field(..., description="문제 ID")
    answer: str = Field(..., description="사용자 답변")
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "test_session_12345",
                "question_id": "vocab_B1_important_1234",
                "answer": "A"
            }
        }

class PronunciationAnalysisRequest(BaseModel):
    audio_base64: str = Field(..., description="Base64 인코딩된 오디오 데이터")
    target_text: str = Field(..., description="발음할 대상 텍스트")
    user_level: str = Field("B1", description="사용자 레벨 (A1-C2)")
    language: str = Field("en", description="언어 코드")
    user_id: Optional[str] = Field(None, description="사용자 ID (데이터 저장용)")
    session_id: Optional[str] = Field(None, description="세션 ID (데이터 저장용)")
    save_to_database: bool = Field(False, description="데이터베이스 저장 여부")
    
    class Config:
        json_schema_extra = {
            "example": {
                "audio_base64": "UklGRnoGAABXQVZFZm10IBAAAAABAAEA...",
                "target_text": "Hello, how are you?",
                "user_level": "B1",
                "language": "en"
            }
        }

# 교정된 발음 생성 요청 모델
class PronunciationCorrectionRequest(BaseModel):
    user_id: str = Field(..., description="사용자 고유 ID")
    target_text: str = Field(..., description="교정할 대상 텍스트")
    user_audio_base64: str = Field(..., description="사용자 발음 오디오 (Base64)")
    user_level: str = Field("B1", description="사용자 레벨 (A1-C2)")
    language: str = Field("en", description="언어 코드")
    session_id: Optional[str] = Field(None, description="세션 ID")

class PronunciationComparisonRequest(BaseModel):
    audio_base64: str = Field(..., description="Base64 인코딩된 오디오 데이터")
    reference_word: str = Field(..., description="비교할 단어")
    user_level: str = Field("B1", description="사용자 레벨 (A1-C2)")
    language: str = Field("en", description="언어 코드")
    
    class Config:
        json_schema_extra = {
            "example": {
                "audio_base64": "UklGRnoGAABXQVZFZm10IBAAAAABAAEA...",
                "reference_word": "computer",
                "user_level": "B1",
                "language": "en"
            }
        }

class PronunciationResponse(BaseModel):
    success: bool = Field(..., description="분석 성공 여부")
    message: str = Field(..., description="응답 메시지")
    data: Optional[Dict] = Field(None, description="분석 결과 데이터")
    error: Optional[str] = Field(None, description="오류 메시지")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "발음 분석이 완료되었습니다.",
                "data": {
                    "overall_score": 85.3,
                    "pitch_score": 82.1,
                    "rhythm_score": 88.7
                },
                "error": None
            }
        }

class GrammarStartRequest(BaseModel):
    user_id: str
    language: str
    level: str

class GrammarAnswerRequest(BaseModel):
    session_id: str
    question_id: str
    answer: str

class VoiceCloneRequest(BaseModel):
    user_id: str = Field(..., description="사용자 고유 ID")
    voice_sample_base64: str = Field(..., description="Base64 인코딩된 음성 샘플")
    voice_name: Optional[str] = Field(None, description="음성 클론 이름")
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user123",
                "voice_sample_base64": "UklGRnoGAABXQVZFZm10IBAAAAABAAEA...",
                "voice_name": "My Voice Clone"
            }
        }

class PersonalizedCorrectionRequest(BaseModel):
    user_id: str = Field(..., description="요청하는 사용자의 고유 ID")
    session_id: str = Field(..., description="발음 분석 시 반환된 세션 ID")

# === 도우미 함수들 ===

async def generate_personalized_learning_path(level: str, weak_areas: List[str]) -> Dict:
    """개인화된 학습 경로 생성"""
    
    # 레벨별 기본 커리큘럼
    base_curriculum = {
        "A1": {
            "weeks": 8,
            "topics": ["Basic greetings", "Numbers", "Family", "Food", "Colors", "Daily routine"],
            "focus_skills": ["vocabulary", "basic_grammar"]
        },
        "A2": {
            "weeks": 10,
            "topics": ["Past experiences", "Future plans", "Shopping", "Travel", "Health", "Weather"],
            "focus_skills": ["past_tense", "future_tense", "conversation"]
        },
        "B1": {
            "weeks": 12,
            "topics": ["Work", "Education", "Technology", "Environment", "Culture", "Relationships"],
            "focus_skills": ["complex_grammar", "reading_comprehension"]
        },
        "B2": {
            "weeks": 14,
            "topics": ["Business", "Academic writing", "Debates", "Literature", "Science", "Politics"],
            "focus_skills": ["writing", "critical_thinking"]
        },
        "C1": {
            "weeks": 16,
            "topics": ["Advanced writing", "Professional communication", "Academic research", "Nuanced expression"],
            "focus_skills": ["advanced_writing", "formal_communication"]
        },
        "C2": {
            "weeks": 18,
            "topics": ["Native-level expression", "Specialized vocabulary", "Cultural nuances", "Professional expertise"],
            "focus_skills": ["perfection", "specialization"]
        }
    }
    
    curriculum = base_curriculum.get(level, base_curriculum["B1"])
    
    # 약점에 따른 커리큘럼 조정
    if weak_areas:
        # 약점 영역에 더 많은 시간 할당
        for week in range(curriculum["weeks"]):
            if week % 3 == 0:  # 매 3주마다 약점 집중 주간
                curriculum[f"week_{week+1}_focus"] = f"Intensive {weak_areas[0]} practice"
    
    return curriculum

async def get_first_lesson_for_level(level: str, weak_areas: List[str]) -> Dict:
    """레벨과 약점에 맞는 첫 번째 레슨"""
    
    # 약점이 있으면 해당 영역부터 시작
    if weak_areas:
        primary_focus = weak_areas[0]
    else:
        primary_focus = "vocabulary"  # 기본값
    
    lesson_topics = {
        "A1": {
            "vocabulary": "Essential everyday words (100 most common words)",
            "grammar": "Basic sentence structure (Subject + Verb + Object)",
            "reading": "Simple texts about daily life",
            "listening": "Basic greetings and introductions"
        },
        "A2": {
            "vocabulary": "Expanded vocabulary (300+ words for common situations)",
            "grammar": "Past and future tenses",
            "reading": "Short stories and simple news",
            "listening": "Conversations about familiar topics"
        },
        "B1": {
            "vocabulary": "Academic and professional vocabulary",
            "grammar": "Complex sentence structures",
            "reading": "News articles and opinion pieces",
            "listening": "Podcasts and lectures"
        },
        "B2": {
            "vocabulary": "Advanced vocabulary and idioms",
            "grammar": "Advanced grammar and style",
            "reading": "Literature and academic texts",
            "listening": "Movies and debates"
        }
    }
    
    topic = lesson_topics.get(level, lesson_topics["A2"]).get(primary_focus, "General practice")
    
    return {
        "lesson_id": f"lesson_1_{level}_{primary_focus}",
        "title": f"{level} Level: {topic}",
        "focus_area": primary_focus,
        "estimated_duration": "15-20 minutes",
        "lesson_type": "interactive_practice",
        "preview": f"Let's start with {primary_focus} practice at {level} level!"
    }

def generate_daily_goals(level: str) -> List[str]:
    """일일 학습 목표 생성"""
    goals_by_level = {
        "A1": [
            "Learn 5 new basic words",
            "Practice simple sentences for 10 minutes",
            "Complete 1 grammar exercise"
        ],
        "A2": [
            "Learn 7 new words with examples",
            "Practice conversation for 15 minutes", 
            "Read one short article"
        ],
        "B1": [
            "Learn 10 new vocabulary words",
            "Write a short paragraph",
            "Listen to a 5-minute audio clip"
        ],
        "B2": [
            "Study advanced grammar for 20 minutes",
            "Read and summarize a news article",
            "Practice speaking on a given topic"
        ],
        "C1": [
            "Analyze complex texts for 30 minutes",
            "Practice formal writing",
            "Engage in advanced discussions"
        ],
        "C2": [
            "Perfect nuanced language use",
            "Study specialized vocabulary",
            "Practice professional presentations"
        ]
    }
    
    return goals_by_level.get(level, goals_by_level["B1"])

def generate_weekly_plan(level: str, weak_areas: List[str]) -> Dict:
    """주간 학습 계획"""
    
    base_plan = {
        "monday": "Vocabulary focus",
        "tuesday": "Grammar practice", 
        "wednesday": "Reading comprehension",
        "thursday": "Listening skills",
        "friday": "Speaking practice",
        "saturday": "Writing exercises",
        "sunday": "Review and assessment"
    }
    
    # 약점 영역에 추가 시간 할당
    if weak_areas:
        for i, weak_area in enumerate(weak_areas[:2]):  # 최대 2개 약점
            day = ["tuesday", "thursday"][i % 2]
            base_plan[day] += f" + Extra {weak_area} practice"
    
    return base_plan

def generate_milestones(level: str) -> List[Dict]:
    """학습 마일스톤 목표"""
    
    milestones_by_level = {
        "A1": [
            {"week": 2, "goal": "Complete basic vocabulary (100 words)", "test": "vocabulary_quiz"},
            {"week": 4, "goal": "Form simple sentences", "test": "sentence_formation"},
            {"week": 6, "goal": "Have basic conversations", "test": "conversation_practice"},
            {"week": 8, "goal": "Ready for A2 level", "test": "level_progression"}
        ],
        "A2": [
            {"week": 3, "goal": "Master past tense", "test": "grammar_test"},
            {"week": 6, "goal": "Read simple stories", "test": "reading_comprehension"},
            {"week": 8, "goal": "Express future plans", "test": "speaking_assessment"},
            {"week": 10, "goal": "Ready for B1 level", "test": "level_progression"}
        ],
        "B1": [
            {"week": 4, "goal": "Understand complex texts", "test": "reading_assessment"},
            {"week": 8, "goal": "Express opinions clearly", "test": "speaking_test"},
            {"week": 12, "goal": "Ready for B2 level", "test": "comprehensive_test"}
        ]
    }
    
    return milestones_by_level.get(level, milestones_by_level["A2"])

def _get_grade_from_score(score: float) -> str:
    """점수를 등급으로 변환"""
    if score >= 90:
        return "A"
    elif score >= 80:
        return "B"
    elif score >= 70:
        return "C"
    elif score >= 60:
        return "D"
    else:
        return "F"

def _get_improvement_priority(result) -> List[str]:
    """개선 우선순위 결정"""
    scores = {
        'pitch': result.pitch_score,
        'rhythm': result.rhythm_score,
        'stress': result.stress_score,
        'fluency': result.fluency_score
    }
    
    # 점수가 낮은 순서로 정렬
    sorted_areas = sorted(scores.items(), key=lambda x: x[1])
    
    priority = []
    for area, score in sorted_areas:
        if score < 80:
            if area == 'pitch':
                priority.append("억양 패턴 연습")
            elif area == 'rhythm':
                priority.append("말하기 리듬 개선")
            elif area == 'stress':
                priority.append("강세 위치 연습")
            elif area == 'fluency':
                priority.append("유창성 향상")
    
    return priority[:3]  # 상위 3개만

def _calculate_similarity(comparison_result: Dict) -> float:
    """발음 유사도 계산"""
    try:
        user_scores = comparison_result.get('user_pronunciation', {})
        overall_score = user_scores.get('overall_score', 60)
        
        # 100점 기준을 유사도 퍼센트로 변환
        similarity = min(100, max(0, overall_score))
        return round(similarity, 1)
    except:
        return 60.0

def _get_practice_recommendation(comparison_result: Dict) -> str:
    """연습 추천사항 생성"""
    
    improvement_areas = comparison_result.get('improvement_areas', [])
    
    if not improvement_areas:
        return "발음이 매우 좋습니다! 현재 수준을 유지하세요."
    
    recommendations = {
        'pitch': "억양 연습: 문장의 중요한 부분에서 목소리 높낮이를 조절해보세요.",
        'rhythm': "리듬 연습: 일정한 속도로 말하는 연습을 해보세요.",
        'stress': "강세 연습: 중요한 음절을 더 강하게 발음해보세요.",
        'fluency': "유창성 연습: 끊어지지 않고 자연스럽게 말하는 연습을 해보세요."
    }
    
    main_area = improvement_areas[0] if improvement_areas else 'pitch'
    return recommendations.get(main_area, "발음 연습을 계속 해보세요.")

# === 기본 라우트 ===

@app.get("/", tags=["System"], summary="API 상태 확인")
async def root():
    """
    API 서버의 기본 상태와 정보를 확인합니다.
    
    - **status**: 서버 상태
    - **version**: API 버전  
    - **features**: 지원하는 기능 목록
    """
    return {
        "message": "AI Language Learning API with Data Collection & Fine-tuning",
        "status": "running",
        "version": "3.0.0",
        "features": [
            "scenario_conversations", 
            "openai_gpt4", 
            "voice_support", 
            "hybrid_mode",
            "adaptive_level_testing",
            "personalized_learning_paths",
            "data_collection",
            "fine_tuning",
            "pronunciation_analysis"
        ],
        "data_collection": "enabled",
        "fine_tuning": "available",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health", tags=["System"], summary="서비스 상태 체크 (데이터 수집 포함)")
async def enhanced_health_check():
    """모든 서비스의 상태를 확인합니다."""
    
    # 기존 서비스 상태 확인
    services_status = {
        "conversation_ai": True,
        "speech_recognition": True,
        "text_to_speech": True,
        "openai_gpt4": True,
        "level_test": True,
        "data_collection": True,  # 새로 추가
        "fine_tuning": True       # 새로 추가
    }
    
    try:
        # 기존 서비스 체크
        situations = conversation_ai_service.get_available_situations()
        services_status["conversation_ai"] = len(situations) > 0
        
        supported_langs = stt_service.get_supported_languages()
        services_status["speech_recognition"] = len(supported_langs) > 0
        
        tts_langs = tts_service.get_supported_languages()
        services_status["text_to_speech"] = len(tts_langs) > 0
        
        openai_status = await openai_service.test_connection()
        services_status["openai_gpt4"] = openai_status.get("connected", False)
        
        services_status["level_test"] = level_test_service is not None
        
        # 데이터 수집 상태 확인
        try:
            stats = await data_collector.get_statistics()
            services_status["data_collection"] = stats.get("total_turns", 0) >= 0
        except Exception as e:
            logger.error(f"데이터 수집 상태 확인 오류: {e}")
            services_status["data_collection"] = False
        
        # Fine-tuning 서비스 상태 확인
        try:
            readiness = await fine_tuning_manager.check_data_readiness("airport")
            services_status["fine_tuning"] = "error" not in readiness
        except Exception as e:
            logger.error(f"Fine-tuning 서비스 상태 확인 오류: {e}")
            services_status["fine_tuning"] = False
        
    except Exception as e:
        logger.error(f"서비스 상태 확인 오류: {e}")
        services_status["error"] = str(e)
    
    all_healthy = all(status for key, status in services_status.items() if key != "error")
    
    return {
        "healthy": all_healthy,
        "services": services_status,
        "data_collection_active": services_status["data_collection"],
        "fine_tuning_available": services_status["fine_tuning"],
        "timestamp": datetime.now().isoformat()
    }

# === 사용자 초기화 및 레벨 테스트 API ===

@app.post("/api/user/initialize", tags=["User"], 
         summary="신규 사용자 초기화",
         description="새로운 사용자를 초기화하고 레벨 테스트를 시작합니다.")
async def initialize_user(
    user_id: str = Query(..., description="사용자 고유 ID"),
    language: str = Query("english", description="학습할 언어")
):
    """신규 사용자 초기화 - 레벨 테스트부터 시작"""
    try:
        logger.info(f"사용자 초기화: {user_id}")
        
        # 레벨 테스트 시작
        test_result = await level_test_service.start_level_test(
            user_id=user_id,
            language=language
        )
        
        if test_result["success"]:
            return {
                "success": True,
                "message": "환영합니다! 먼저 간단한 레벨 테스트를 진행하겠습니다.",
                "data": {
                    "user_id": user_id,
                    "step": "level_assessment", 
                    "test_session": test_result,
                    "instructions": "각 문제를 차례대로 풀어주세요. 모르는 문제는 추측해서 답해도 괜찮습니다."
                }
            }
        else:
            raise HTTPException(status_code=400, detail=test_result["error"])
            
    except Exception as e:
        logger.error(f"사용자 초기화 오류: {e}")
        raise HTTPException(status_code=500, detail=f"사용자 초기화 중 오류: {str(e)}")

@app.post("/api/level-test/start", tags=["Level Test"], summary="레벨 테스트 시작")
async def start_level_test(request: LevelTestStartRequest):
    try:
        logger.info(f"레벨 테스트 시작 요청: {request.user_id} - {request.language}")
        result = await level_test_service.start_level_test(user_id=request.user_id, language=request.language)
        if result["success"]:
            return result
        # 서비스에서 실패 시 반환된 오류 메시지를 사용하여 예외 발생
        raise HTTPException(status_code=400, detail=result.get("error", "레벨 테스트를 시작할 수 없습니다."))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"레벨 테스트 시작 중 예상치 못한 오류: {e}")
        # 중앙 핸들러가 처리하도록 예외를 다시 발생시킴
        raise

@app.post("/api/level-test/answer", tags=["Level Test"], summary="레벨 테스트 답변 제출")
async def submit_test_answer(request: LevelTestAnswerRequest):
    try:
        logger.info(f"레벨 테스트 답변 제출: {request.session_id} - {request.question_id}")
        result = await level_test_service.submit_answer(session_id=request.session_id, question_id=request.question_id, answer=request.answer)
        if result["success"]:
            return {"success": True, "message": "답변이 처리되었습니다.", "data": result}
        raise HTTPException(status_code=400, detail=result.get("error", "답변 처리에 실패했습니다."))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"답변 처리 중 예상치 못한 오류: {e}")
        raise

@app.get("/api/level-test/{session_id}/status", tags=["Level Test"],
        summary="레벨 테스트 상태 조회",
        description="현재 진행 중인 레벨 테스트의 상태를 조회합니다.")
async def get_level_test_status(session_id: str):
    """레벨 테스트 상태 조회"""
    try:
        status = level_test_service.get_session_status(session_id)
        
        return {
            "success": True,
            "session_id": session_id,
            "status": status,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"레벨 테스트 상태 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=f"상태 조회 중 오류: {str(e)}")

@app.get("/api/level-test/{session_id}/results", tags=["Level Test"],
        summary="레벨 테스트 결과 조회",
        description="완료된 레벨 테스트의 상세 결과를 조회합니다.")
async def get_level_test_results(session_id: str):
    """레벨 테스트 상세 결과 조회"""
    try:
        session = level_test_service.active_sessions.get(session_id)
        
        if not session:
            raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
        
        if not session["completed"]:
            raise HTTPException(status_code=400, detail="아직 완료되지 않은 테스트입니다.")
        
        results = session.get("final_result", {})
        
        return {
            "success": True,
            "session_id": session_id,
            "results": results
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"결과 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=f"결과 조회 중 오류: {str(e)}")

@app.post("/api/level-test/start-mini")
async def start_mini_test_endpoint(request: dict):
    """3문제짜리 미니 어휘력 테스트를 시작합니다."""
    user_id = request.get("user_id")
    language = request.get("language", "english")
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")

    return await level_test_service.start_mini_vocab_test(user_id=user_id, language=language)


@app.post("/api/user/complete-assessment", tags=["User"],
          summary="레벨 평가 완료",
          description="레벨 테스트 완료 후 개인화된 학습 경로를 제공합니다.")
async def complete_assessment(
        user_id: str = Query(..., description="사용자 ID"),
        session_id: str = Query(..., description="테스트 세션 ID")
):
    """레벨 테스트를 공식적으로 완료 처리하고 최종 결과를 생성하여 반환합니다."""
    try:
        # 이 함수는 내부적으로 답변 갯수를 확인하고, 부족하면 ValueError를 발생시킵니다.
        final_result = await level_test_service.finalize_test_session(session_id)

        # 사용자 프로필 데이터는 final_result에 이미 포함되어 있습니다.
        user_profile = {
            "user_id": user_id,
            "assessed_level": final_result.get("final_level", "A2"),
            "skill_breakdown": final_result.get("skill_breakdown", {}),
            "strengths": final_result.get("strengths", []),
            "areas_to_improve": final_result.get("areas_to_improve", []),
            "assessment_date": datetime.now().isoformat()
        }

        # 앱에서 필요한 추가 학습 정보 생성
        learning_plan = {
            "first_lesson": await get_first_lesson_for_level(user_profile["assessed_level"], user_profile["areas_to_improve"]),
            "daily_goals": generate_daily_goals(user_profile["assessed_level"]),
            "recommendations": final_result.get("recommendations", []),
            "next_steps": final_result.get("next_steps", [])
        }

        logger.info(f"사용자 평가 완료: {user_id} - 레벨: {user_profile['assessed_level']}")

        # 최종 응답 데이터 구성
        return {
            "success": True,
            "message": f"축하합니다! 당신의 레벨은 {user_profile['assessed_level']}입니다.",
            "data": {
                "user_profile": user_profile,
                **learning_plan
            }
        }

    except ValueError as e:
        logger.warning(f"평가 완료 실패 (400): {session_id} - {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"평가 완료 처리 중 심각한 오류: {e}")
        raise HTTPException(status_code=500, detail=f"평가 완료 처리 중 서버 오류가 발생했습니다: {str(e)}")
    
# === 대화 관리 API (데이터 수집 포함) ===

@app.post("/api/conversation/start", tags=["Conversation"],
          summary="대화 세션 시작 (데이터 수집 포함)",
          description="새로운 대화 세션을 시작하고 데이터 수집을 활성화합니다.",
          response_model=ConversationResponse)
async def start_conversation_with_data_collection(request: ConversationStartRequest):
    """새로운 대화 세션 시작 (데이터 수집 포함)"""

    try:
        logger.info(f"대화 시작 요청 (데이터 수집): {request.user_id} - {request.situation}")

        session_id = f"{request.user_id}_{request.situation}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # ▼▼▼ [수정 1/2] service 호출 시 'translate' 파라미터를 전달합니다. ▼▼▼
        result = await conversation_ai_service.start_conversation(
            session_id=session_id,
            situation=request.situation,
            difficulty=request.difficulty,
            language=request.language,
            mode=request.mode,
            user_id=request.user_id,
            translate=request.translate # <--- 이 줄이 추가되었습니다.
        )

        if result["success"]:
            # ▼▼▼ [수정 2/2] 변경된 'result' 구조에 맞춰 데이터를 가져옵니다. ▼▼▼

            # 1. service가 반환한 'data' 딕셔너리를 가져옵니다.
            service_data = result.get("data", {})

            # 2. 'data' 딕셔너리 안에서 필요한 값들을 꺼냅니다.
            response_data = {
                "session_id": service_data.get("session_id"),
                "situation": request.situation,
                "difficulty": request.difficulty,
                "language": request.language,
                "mode": service_data.get("mode"),
                "scenario_title": service_data.get("scenario_title"),
                "ai_message": service_data.get("ai_message"),
                "translated_text": service_data.get("translated_text"), # 번역문 추가
                "features": service_data.get("features", []),
                "scenario_context": service_data.get("scenario_context", {}),
                "available_situations": conversation_ai_service.get_available_situations(),
                "data_collection_enabled": service_data.get("data_collection_enabled", False)
            }

            if "expected_responses" in service_data:
                response_data["expected_responses"] = service_data["expected_responses"]

            # ▲▲▲ 여기까지 수정 ▲▲▲

            logger.info(f"대화 세션 시작 성공 (데이터 수집): {session_id}")

            return ConversationResponse(
                success=True,
                message="대화 세션이 시작되었습니다. 데이터 수집이 활성화되었습니다.",
                data=response_data
            )
        else:
            logger.warning(f"대화 시작 실패: {result['error']}")
            raise HTTPException(status_code=400, detail=result["error"])

    except Exception as e:
        logger.error(f"대화 시작 오류: {e}")
        import traceback
        logger.error(traceback.format_exc()) # 더 자세한 오류 로그를 위해 추가
        raise HTTPException(status_code=500, detail=f"대화 시작 중 오류: {str(e)}")

@app.post("/api/conversation/text", tags=["Conversation"],
         summary="텍스트 메시지 전송",
         description="대화 세션에 텍스트 메시지를 전송하고 AI 응답을 받습니다.",
         response_model=ConversationResponse)
async def send_text_message(request: TextMessageRequest):
    """텍스트 메시지 처리 (데이터 수집 포함)"""

    try:
        logger.info(f"텍스트 메시지: {request.session_id} - {request.message[:50]}...")

        # 입력 검증
        if not request.message or request.message.strip() == "":
            raise HTTPException(status_code=400, detail="메시지가 비어있습니다.")

        # 향상된 대화 AI 처리 (데이터 수집 포함)
        result = await conversation_ai_service.process_user_response(
            session_id=request.session_id,
            user_message=request.message,
            translate=request.translate
        )

        if result["success"]:
            # TTS로 AI 응답 음성 생성
            ai_audio = None
            try:
                if result.get("ai_message") and not result.get("completed", False):
                    ai_audio = await tts_service.text_to_speech_base64(
                        text=result["ai_message"],
                        language=request.language[:2]  # 'en-US' -> 'en'
                    )
            except Exception as tts_error:
                logger.warning(f"TTS 생성 실패: {tts_error}")
                ai_audio = None

            # 기본 피드백 구조 보장
            feedback = result.get("feedback", {})
            if not isinstance(feedback, dict):
                feedback = {}

            # 필수 피드백 키들 보장
            feedback.setdefault("level", "good")
            feedback.setdefault("message", "잘했어요! 계속 연습해보세요.")
            feedback.setdefault("accuracy", 0.85)
            feedback.setdefault("grammar_score", 0.9)
            feedback.setdefault("suggestions", [])

            # 단계 정보 계산
            step = result.get("step", 1)
            total_steps = result.get("total_steps", 5)
            completed = result.get("completed", False)

            # 응답 데이터 구성
            response_data = {
                "session_id": request.session_id,
                "mode": result.get("mode", "unknown"),
                "user_message": request.message,
                "ai_message": result.get("ai_message", ""),
                "ai_audio_base64": ai_audio,
                "feedback": feedback,
                "step": step,
                "total_steps": total_steps,
                "completed": completed,
                "translated_text": result.get("translated_text")
            }

            # 모드별 추가 데이터
            if result.get("mode") in ["openai", "hybrid"]:
                response_data.update({
                    "turn_count": result.get("turn_count", 0),
                    "tokens_used": result.get("tokens_used", 0),
                    "model": result.get("model", "gpt-4")
                })
            elif result.get("mode") == "scenario":
                response_data.update({
                    "expected_responses": result.get("expected_responses", [])
                })

            # 완료시 요약 추가
            if completed:
                summary = result.get("summary", {})
                if not summary:
                    # 기본 요약 생성
                    summary = {
                        "total_responses": step,
                        "average_accuracy": feedback.get("accuracy", 0.85),
                        "areas_to_improve": feedback.get("suggestions", ["pronunciation", "grammar"]),
                        "completion_time": datetime.now().isoformat(),
                        "session_id": request.session_id
                    }
                response_data["summary"] = summary

            logger.info(f"텍스트 처리 성공: {request.session_id}")

            return ConversationResponse(
                success=True,
                message="메시지가 처리되었습니다.",
                data=response_data
            )
        else:
            error_msg = result.get("error", "알 수 없는 오류가 발생했습니다.")
            logger.warning(f"텍스트 처리 실패: {error_msg}")
            raise HTTPException(status_code=400, detail=error_msg)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"텍스트 처리 오류: {e}")
        import traceback
        logger.error(f"상세 오류: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"텍스트 처리 중 오류가 발생했습니다: {str(e)}")

@app.post("/api/conversation/voice", tags=["Conversation"],
          summary="음성 메시지 전송",
          description="음성 메시지를 텍스트로 변환하여 대화에 사용합니다.",
          response_model=ConversationResponse)
async def send_voice_message(request: VoiceMessageRequest):
    """음성 메시지 처리"""

    try:
        logger.info(f"음성 메시지: {request.session_id}")

        # STT로 음성을 텍스트로 변환
        recognized_text = await stt_service.recognize_from_base64(
            audio_base64=request.audio_base64,
            language=request.language
        )

        # ▼▼▼ [수정] 음성 인식 실패 시 오류 메시지 변경 ▼▼▼
        if not recognized_text:
            # 400 Bad Request: 클라이언트의 요청이 잘못됨 (음성 데이터가 불분명)
            raise HTTPException(status_code=400, detail="목소리를 인식할 수 없습니다. 주변 소음이 없는 곳에서 다시 시도해주세요.")

        logger.info(f"음성 인식 결과: {recognized_text}")

        # 텍스트 메시지로 처리
        text_request = TextMessageRequest(
            session_id=request.session_id,
            message=recognized_text,
            language=request.language,
            translate=request.translate
        )

        # 1. send_text_message가 반환하는 ConversationResponse 객체를 받습니다.
        response_model = await send_text_message(text_request)

        # 2. Pydantic 모델을 딕셔너리로 변환하여 수정합니다.
        response_dict = response_model.model_dump()

        # 3. 'data' 필드에 음성 인식 결과를 추가합니다.
        if "data" in response_dict and response_dict["data"] is not None:
            response_dict["data"]["recognized_text"] = recognized_text
            response_dict["data"]["original_audio"] = True

        # 4. 수정된 딕셔너리를 JSON 응답으로 반환합니다.
        return JSONResponse(content=response_dict)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"음성 처리 오류: {e}")
        raise HTTPException(status_code=500, detail=f"음성 처리 중 오류: {str(e)}")

@app.get("/api/conversation/{session_id}/status", tags=["Conversation"],
        summary="대화 세션 상태 조회",
        description="진행 중인 대화 세션의 상태를 조회합니다.")
async def get_conversation_status(session_id: str):
    """대화 세션 상태 조회"""
    
    try:
        # 세션 상태 조회
        session_status = conversation_ai_service.get_session_status(session_id)
        
        # 기본 상태 구조 보장
        if session_status.get("exists", False):
            status_data = {
                "exists": True,
                "current_step": session_status.get("current_step", 1),
                "total_steps": session_status.get("total_steps", 5),
                "responses_count": session_status.get("responses_count", 0),
                "situation": session_status.get("situation", "unknown"),
                "language": session_status.get("language", "en"),
                "mode": session_status.get("mode", "unknown"),
                "started_at": session_status.get("started_at", datetime.now().isoformat()),
                "last_activity": session_status.get("last_activity", datetime.now().isoformat()),
                "data_collection": session_status.get("data_collection", False)
            }
        else:
            status_data = {
                "exists": False,
                "message": "세션을 찾을 수 없습니다."
            }
        
        return {
            "success": True,
            "session_id": session_id,
            "status": status_data,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"세션 상태 조회 오류: {e}")
        # 세션이 존재하지 않는 경우에도 정상 응답
        return {
            "success": True,
            "session_id": session_id,
            "status": {
                "exists": False,
                "message": f"세션 조회 중 오류: {str(e)}"
            },
            "timestamp": datetime.now().isoformat()
        }

@app.delete("/api/conversation/{session_id}", tags=["Conversation"],
           summary="대화 세션 종료",
           description="진행 중인 대화 세션을 종료합니다.")
async def end_conversation(session_id: str):
    """대화 세션 종료"""
    
    try:
        # 향상된 세션 종료 (데이터 수집 포함)
        result = await conversation_ai_service.end_conversation(session_id)
        
        # WebSocket 연결 정리
        if session_id in connected_clients:
            del connected_clients[session_id]
        
        logger.info(f"대화 세션 종료: {session_id}")
        
        return {
            "success": True,
            "message": "대화 세션이 종료되었습니다.",
            "session_id": session_id,
            "summary": result.get("summary", {}),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"세션 종료 오류: {e}")
        # 세션 종료는 항상 성공으로 처리 (이미 종료된 경우도 있음)
        return {
            "success": True,
            "message": "대화 세션 종료 처리가 완료되었습니다.",
            "session_id": session_id,
            "note": f"처리 중 알림: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }

# === 데이터 수집 API ===

@app.post("/api/conversation/feedback", tags=["Data Collection"],
         summary="대화 피드백 제출",
         description="사용자가 특정 대화 턴에 대한 만족도와 피드백을 제공합니다.")
async def submit_conversation_feedback(request: FeedbackRequest):
    """대화 피드백 수집"""
    
    try:
        await data_collector.update_user_feedback(
            session_id=request.session_id,
            turn_index=request.turn_index,
            satisfaction=request.satisfaction,
            feedback_comment=request.feedback_comment
        )
        
        logger.info(f"피드백 수집: {request.session_id}#{request.turn_index} = {request.satisfaction}")
        
        return {
            "success": True,
            "message": "피드백이 성공적으로 저장되었습니다.",
            "data": {
                "session_id": request.session_id,
                "turn_index": request.turn_index,
                "satisfaction": request.satisfaction,
                "submitted_at": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"피드백 저장 오류: {e}")
        raise HTTPException(status_code=500, detail=f"피드백 저장 중 오류: {str(e)}")

@app.get("/api/data/statistics", tags=["Data Collection"],
        summary="수집된 데이터 통계",
        description="수집된 대화 데이터의 통계 정보를 조회합니다.")
async def get_data_statistics():
    """데이터 수집 통계 조회"""
    
    try:
        stats = await data_collector.get_statistics()
        
        return {
            "success": True,
            "message": "데이터 통계 조회 성공",
            "data": stats,
            "retrieved_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"통계 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=f"통계 조회 중 오류: {str(e)}")

@app.get("/api/data/training-ready", tags=["Data Collection"],
        summary="Fine-tuning 준비 상태",
        description="상황별로 Fine-tuning을 위한 충분한 데이터가 수집되었는지 확인합니다.")
async def check_training_readiness():
    """Fine-tuning 준비 상태 확인"""
    
    try:
        stats = await data_collector.get_statistics()
        fine_tuning_ready = stats.get('fine_tuning_ready', {})
        
        # 전체 준비 상태 계산
        total_ready_situations = sum(1 for situation_data in fine_tuning_ready.values() if situation_data.get('ready', False))
        
        return {
            "success": True,
            "data": {
                "situations": fine_tuning_ready,
                "total_ready_situations": total_ready_situations,
                "total_situations": len(fine_tuning_ready),
                "overall_ready": total_ready_situations >= 2,  # 최소 2개 상황 준비
                "recommendation": "더 많은 사용자 피드백이 필요합니다" if total_ready_situations < 2 else "Fine-tuning을 시작할 수 있습니다"
            }
        }
        
    except Exception as e:
        logger.error(f"준비 상태 확인 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/data/export/{situation}", tags=["Data Collection"],
        summary="훈련 데이터 내보내기",
        description="특정 상황의 고품질 대화 데이터를 훈련용으로 내보냅니다.")
async def export_training_data(
    situation: str,
    min_satisfaction: float = Query(0.7, description="최소 만족도"),
    limit: int = Query(500, description="최대 데이터 수")
):
    """훈련 데이터 내보내기"""
    
    if situation not in ["airport", "restaurant", "hotel", "street"]:
        raise HTTPException(status_code=400, detail="지원하지 않는 상황입니다.")
    
    try:
        training_data = await data_collector.get_training_data(
            situation=situation,
            min_satisfaction=min_satisfaction,
            limit=limit
        )
        
        if len(training_data) < 10:
            return {
                "success": False,
                "message": f"데이터 부족: {situation}에 대한 충분한 고품질 데이터가 없습니다. (현재: {len(training_data)}개, 최소 필요: 10개)",
                "data": {
                    "current_count": len(training_data),
                    "required_minimum": 10,
                    "situation": situation
                }
            }
        
        return {
            "success": True,
            "message": f"{situation} 상황의 훈련 데이터를 성공적으로 내보냈습니다.",
            "data": {
                "situation": situation,
                "total_count": len(training_data),
                "min_satisfaction": min_satisfaction,
                "training_data": training_data,
                "exported_at": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"훈련 데이터 내보내기 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/pronunciation/ssml-correction", tags=["Pronunciation"])
async def generate_ssml_corrected_pronunciation(request: SSMLCorrectionRequest):
    """
    [개선된 통합 API] 사용자 발음을 분석하고, 점수와 레벨에 따라
    SSML로 상세 교정한 음성을 생성합니다.
    """
    try:
        # --- 1. 발음 분석 (세부 점수 활용) ---
        analysis_result = await pronunciation_service.analyze_pronunciation_from_base64(
            audio_base64=request.user_audio_base64,
            target_text=request.target_text,
            user_level=request.user_level,
            language=request.language
        )

        # --- 2. 고급 SSML 생성 (분석 결과 기반 동적 생성) ---
        words_and_punctuations = re.findall(r"[\w']+|[.,!?]", request.target_text)
        ssml_parts = []
        scores = analysis_result.scores
        low_score_areas = {area for area, score in scores.items() if score < 80}

        for item in words_and_punctuations:
            if re.match(r"[\w']+", item): # 단어인 경우
                word = item
                correct_ipa = pronunciation_service.core_service.data_manager.get_ipa_for_word(word)
                if correct_ipa:
                    phoneme_tag = f'<phoneme alphabet="ipa" ph="{correct_ipa}">{word}</phoneme>'
                    # 강세(stress) 점수가 낮으면 emphasis 태그 추가
                    ssml_parts.append(f'<emphasis level="strong">{phoneme_tag}</emphasis>' if 'stress' in low_score_areas else phoneme_tag)
                else:
                    ssml_parts.append(word)
            else: # 구두점인 경우
                # 리듬(rhythm) 점수가 낮으면 구두점 뒤에 쉬는 시간 추가
                pause = '250ms' if 'rhythm' in low_score_areas else '100ms'
                ssml_parts.append(f'{item}<break time="{pause}"/>')

        ssml_content = ' '.join(ssml_parts)

        # 유창성(fluency) 점수가 낮거나 A1 레벨이면 전체 속도를 느리게 조정
        rate = "slow" if 'fluency' in low_score_areas or request.user_level == "A1" else "medium"
        final_ssml = f'<speak><prosody rate="{rate}">{ssml_content}</prosody></speak>'
        logger.info(f"생성된 최종 SSML: {final_ssml}")

        # --- 3. 음성 생성 (레벨별 설정 적용) ---
        correction_result = await voice_cloning_service._generate_speech_with_voice(
            voice_id=voice_cloning_service.user_voices[request.user_id]['voice_id'],
            text_or_ssml=final_ssml,
            language=request.language,
            user_level=request.user_level
        )

        if correction_result["success"]:
            return {
                "success": True, "message": "SSML 기반 발음 교정이 완료되었습니다.",
                "data": {
                    "original_analysis": analysis_result,
                    "corrected_audio_base64": correction_result["audio_base64"],
                    "generated_ssml": final_ssml
                }
            }
        else:
            raise HTTPException(status_code=500, detail=correction_result.get("error"))

    except Exception as e:
        logger.error(f"SSML 교정 최종 오류: {e}")
        import traceback
        logger.error(f"상세 오류: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

# === Fine-tuning API ===

@app.post("/api/fine-tuning/start/{situation}", tags=["Fine-tuning"],
         summary="상황별 Fine-tuning 시작",
         description="특정 상황에 대한 모델 Fine-tuning을 시작합니다. 충분한 고품질 데이터가 필요합니다.")
async def start_fine_tuning(situation: str):
    """Fine-tuning 시작"""
    
    if situation not in ["airport", "restaurant", "hotel", "street"]:
        raise HTTPException(status_code=400, detail="지원하지 않는 상황입니다. (airport, restaurant, hotel, street)")
    
    try:
        # 데이터 준비 상태 확인
        readiness = await fine_tuning_manager.check_data_readiness(situation)
        
        if not readiness["ready"]:
            raise HTTPException(
                status_code=400, 
                detail=f"데이터 부족: {situation}에 대한 충분한 데이터가 없습니다. "
                       f"현재 {readiness['available_data']}개, 필요 {readiness['required_minimum']}개"
            )
        
        # Fine-tuning 시작
        result = await fine_tuning_manager.start_fine_tuning(situation)
        
        if result["success"]:
            return {
                "success": True,
                "message": f"{situation} 상황에 대한 Fine-tuning이 시작되었습니다.",
                "data": result
            }
        else:
            raise HTTPException(status_code=400, detail=result["error"])
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Fine-tuning 시작 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/fine-tuning/status/{job_id}", tags=["Fine-tuning"],
        summary="Fine-tuning 상태 확인",
        description="Fine-tuning 작업의 진행 상태를 확인합니다.")
async def check_fine_tuning_status(job_id: str):
    """Fine-tuning 상태 확인"""
    
    try:
        status = await fine_tuning_manager.check_fine_tuning_status(job_id)
        
        if "error" in status:
            raise HTTPException(status_code=400, detail=status["error"])
        
        return {
            "success": True,
            "data": status
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"상태 확인 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/fine-tuning/jobs", tags=["Fine-tuning"],
        summary="Fine-tuning 작업 목록",
        description="모든 Fine-tuning 작업의 목록을 조회합니다.")
async def list_fine_tuning_jobs():
    """Fine-tuning 작업 목록"""
    
    try:
        jobs = await fine_tuning_manager.list_fine_tuning_jobs()
        
        return {
            "success": True,
            "data": {
                "jobs": jobs,
                "total_count": len(jobs)
            }
        }
        
    except Exception as e:
        logger.error(f"작업 목록 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/fine-tuning/readiness", tags=["Fine-tuning"],
        summary="모든 상황의 Fine-tuning 준비 상태",
        description="모든 상황별로 Fine-tuning을 위한 데이터 준비 상태를 확인합니다.")
async def check_all_readiness():
    """모든 상황의 Fine-tuning 준비 상태"""
    
    try:
        situations = ["airport", "restaurant", "hotel", "street"]
        readiness_status = {}
        
        for situation in situations:
            readiness_status[situation] = await fine_tuning_manager.check_data_readiness(situation)
        
        # 전체 준비 상태 계산
        ready_count = sum(1 for status in readiness_status.values() if status["ready"])
        
        return {
            "success": True,
            "data": {
                "situations": readiness_status,
                "ready_count": ready_count,
                "total_count": len(situations),
                "overall_ready": ready_count >= 1,  # 최소 1개 상황 준비
                "progress_summary": {
                    situation: f"{status['available_data']}/{status['required_minimum']}"
                    for situation, status in readiness_status.items()
                }
            }
        }
        
    except Exception as e:
        logger.error(f"준비 상태 확인 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/fine-tuning/test/{model_name}", tags=["Fine-tuning"],
         summary="Fine-tuned 모델 테스트",
         description="Fine-tuned 모델을 테스트 메시지로 테스트합니다.")
async def test_fine_tuned_model(
    model_name: str,
    situation: str = Query(..., description="테스트할 상황"),
    test_message: str = Query(..., description="테스트 메시지")
):
    """Fine-tuned 모델 테스트"""
    
    if situation not in ["airport", "restaurant", "hotel", "street"]:
        raise HTTPException(status_code=400, detail="지원하지 않는 상황입니다.")
    
    try:
        result = await fine_tuning_manager.test_fine_tuned_model(
            model_name=model_name,
            situation=situation,
            test_message=test_message
        )
        
        if result.get("success", False):
            return {
                "success": True,
                "message": "Fine-tuned 모델 테스트 완료",
                "data": result
            }
        else:
            raise HTTPException(status_code=400, detail=result.get("error", "테스트 실패"))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"모델 테스트 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
# === 발음 분석 API ===

@app.post("/api/pronunciation/analyze", tags=["Pronunciation"],
          summary="음성 억양 분석 (데이터 저장 포함)",
          description="사용자의 음성을 분석하여 발음, 억양, 리듬 등을 평가하고 선택적으로 데이터베이스에 저장합니다.",
          response_model=PronunciationResponse)
async def analyze_pronunciation_with_storage(request: PronunciationAnalysisRequest):
    """음성 억양 분석 (데이터 저장 기능 포함)"""

    try:
        logger.info(f"억양 분석 요청: {len(request.target_text)} 글자, 레벨: {request.user_level}, 저장: {request.save_to_database}")

        if not request.audio_base64 or not request.target_text:
            raise HTTPException(status_code=400, detail="음성 데이터와 대상 텍스트가 모두 필요합니다.")

        if request.save_to_database and (not request.user_id or not request.session_id):
            raise HTTPException(status_code=400, detail="데이터 저장을 위해서는 user_id와 session_id가 필요합니다.")

        # 억양 분석 서비스 호출
        result = await pronunciation_service.analyze_pronunciation_from_base64(
            audio_base64=request.audio_base64,
            target_text=request.target_text,
            user_level=request.user_level,
            language=request.language,
            user_id=request.user_id if request.save_to_database else None,
            session_id=request.session_id if request.save_to_database else None
        )

        # [핵심 수정] 앱이 사용하기 편하도록 데이터 구조를 평탄화(flatten)합니다.
        response_data = {
            "analysis_id": f"pronunciation_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "target_text": request.target_text,
            "user_level": request.user_level,
            "language": request.language,

            # 'scores' 객체 대신 점수들을 바로 최상위 레벨로 꺼냅니다.
            "overall_score": result.overall_score,
            "pitch_score": result.pitch_score,
            "rhythm_score": result.rhythm_score,
            "stress_score": result.stress_score,
            "fluency_score": result.fluency_score,

            # 'feedback' 객체 대신 피드백들을 바로 최상위 레벨로 꺼냅니다.
            "detailed_feedback": result.detailed_feedback,
            "suggestions": result.suggestions,
            "phoneme_scores": result.phoneme_scores,

            "grade": _get_grade_from_score(result.overall_score),
            "improvement_priority": _get_improvement_priority(result),
            "analyzed_at": datetime.now().isoformat(),
            "data_saved": request.save_to_database,
            "session_id": request.session_id if request.save_to_database else None
        }

        logger.info(f"억양 분석 완료: 전체 점수 {result.overall_score:.1f}, 데이터 저장: {request.save_to_database}")

        return PronunciationResponse(
            success=True,
            message="억양 분석이 완료되었습니다.",
            data=response_data
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"억양 분석 오류: {e}")
        import traceback
        logger.error(f"상세 오류: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"억양 분석 중 오류가 발생했습니다: {str(e)}")

# 통합 발음 교정 API (분석 + 교정 음성 생성 + 데이터 저장)
@app.post("/api/pronunciation/correct-with-voice", tags=["Pronunciation"],
         summary="발음 분석 및 개인화된 교정 음성 생성",
         description="사용자 음성을 분석하고, 사용자의 목소리로 교정된 발음을 생성하여 모든 데이터를 저장합니다.")
async def generate_corrected_pronunciation_with_storage(request: PronunciationCorrectionRequest):
    """발음 분석 + 교정 음성 생성 + 데이터 저장 통합 API"""
    
    try:
        logger.info(f"통합 발음 교정 요청: {request.user_id} - {request.target_text[:30]}...")
        
        # 세션 ID 생성 (제공되지 않은 경우)
        if not request.session_id:
            request.session_id = f"pronunciation_{request.user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # 통합 처리 실행
        result = await pronunciation_service.generate_and_save_corrected_pronunciation(
            user_id=request.user_id,
            session_id=request.session_id,
            target_text=request.target_text,
            user_audio_base64=request.user_audio_base64,
            user_level=request.user_level,
            language=request.language
        )
        
        if result["success"]:
            return {
                "success": True,
                "message": "발음 분석 및 교정이 완료되었습니다.",
                "data": {
                    "session_id": request.session_id,
                    "original_analysis": {
                        "overall_score": result["analysis_result"].overall_score,
                        "pitch_score": result["analysis_result"].pitch_score,
                        "rhythm_score": result["analysis_result"].rhythm_score,
                        "stress_score": result["analysis_result"].stress_score,
                        "fluency_score": result["analysis_result"].fluency_score,
                        "detailed_feedback": result["analysis_result"].detailed_feedback,
                        "suggestions": result["analysis_result"].suggestions
                    },
                    "corrected_audio_base64": result["corrected_audio"].get("corrected_audio_base64"),
                    "corrections_applied": result["corrected_audio"].get("corrections_applied", []),
                    "data_saved": result["data_saved"],
                    "processed_at": datetime.now().isoformat()
                }
            }
        else:
            return {
                "success": False,
                "error": result.get("error", "발음 교정 처리 중 오류가 발생했습니다."),
                "data_saved": result.get("data_saved", False)
            }
            
    except Exception as e:
        logger.error(f"통합 발음 교정 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# 사용자 발음 기록 조회 API
@app.get("/api/pronunciation/history/{user_id}", tags=["Pronunciation"],
        summary="사용자 발음 연습 기록 조회",
        description="특정 사용자의 발음 연습 기록을 조회합니다.")
async def get_user_pronunciation_history(
    user_id: str,
    limit: int = Query(50, description="조회할 기록 수"),
    language: Optional[str] = Query(None, description="언어 필터")
):
    """사용자 발음 연습 기록 조회"""
    
    try:
        history = await pronunciation_data_service.get_user_pronunciation_history(
            user_id=user_id,
            limit=limit
        )
        
        # 언어 필터 적용
        if language:
            history = [h for h in history if h.get('language') == language]
        
        return {
            "success": True,
            "user_id": user_id,
            "total_records": len(history),
            "history": history,
            "retrieved_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"사용자 기록 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# 특정 세션 상세 정보 조회 API
@app.get("/api/pronunciation/session/{session_id}", tags=["Pronunciation"],
        summary="발음 세션 상세 정보 조회",
        description="특정 발음 세션의 상세 정보와 음성 파일들을 조회합니다.")
async def get_pronunciation_session_details(session_id: str):
    """발음 세션 상세 정보 조회"""
    
    try:
        session_details = await pronunciation_data_service.get_pronunciation_session_details(session_id)
        
        if not session_details:
            raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
        
        # 음성 파일들 조회
        audio_files = await pronunciation_data_service.get_audio_files(session_details['id'])
        
        return {
            "success": True,
            "session_details": session_details,
            "audio_files": audio_files,
            "retrieved_at": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"세션 상세 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# 사용자 발음 통계 API
@app.get("/api/pronunciation/statistics/{user_id}", tags=["Pronunciation"],
        summary="사용자 발음 연습 통계",
        description="사용자의 발음 연습 통계 정보를 제공합니다.")
async def get_user_pronunciation_statistics(user_id: str):
    """사용자 발음 연습 통계"""
    
    try:
        statistics = await pronunciation_data_service.get_user_statistics(user_id)
        
        return {
            "success": True,
            "user_id": user_id,
            "statistics": statistics,
            "generated_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"통계 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# 음성 파일 다운로드 API
@app.get("/api/pronunciation/download-audio/{session_id}/{audio_type}", tags=["Pronunciation"],
        summary="음성 파일 다운로드",
        description="특정 세션의 음성 파일을 다운로드합니다.")
async def download_pronunciation_audio(
    session_id: str,
    audio_type: str = Path(..., description="음성 타입 (user_original 또는 corrected_pronunciation)")
):
    """음성 파일 다운로드"""
    
    try:
        if audio_type not in ["user_original", "corrected_pronunciation"]:
            raise HTTPException(status_code=400, detail="올바르지 않은 음성 타입입니다.")
        
        # 세션 상세 정보 조회
        session_details = await pronunciation_data_service.get_pronunciation_session_details(session_id)
        
        if not session_details:
            raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
        
        # 음성 파일 조회
        audio_files = await pronunciation_data_service.get_audio_files(session_details['id'])
        
        if audio_type not in audio_files:
            raise HTTPException(status_code=404, detail="요청한 음성 파일을 찾을 수 없습니다.")
        
        return {
            "success": True,
            "session_id": session_id,
            "audio_type": audio_type,
            "audio_base64": audio_files[audio_type],
            "target_text": session_details.get('target_text', ''),
            "language": session_details.get('language', 'en'),
            "downloaded_at": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"음성 다운로드 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/api/pronunciation/compare", tags=["Pronunciation"],
         summary="발음 비교 분석",
         description="사용자 발음과 표준 발음을 비교 분석합니다.",
         response_model=PronunciationResponse)
async def compare_pronunciation(request: PronunciationComparisonRequest):
    """발음 비교 분석"""
    
    try:
        logger.info(f"발음 비교 요청: {request.reference_word}, 레벨: {request.user_level}")
        
        # 입력 검증
        if not request.audio_base64:
            raise HTTPException(status_code=400, detail="음성 데이터가 없습니다.")
        
        if not request.reference_word:
            raise HTTPException(status_code=400, detail="비교할 단어가 없습니다.")
        
        # 발음 비교 수행
        comparison_result = await pronunciation_service.compare_pronunciations(
            user_audio_base64=request.audio_base64,
            reference_word=request.reference_word,
            user_level=request.user_level
        )
        
        # 응답 데이터 구성
        response_data = {
            "comparison_id": f"comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "reference_word": request.reference_word,
            "user_level": request.user_level,
            "comparison_result": comparison_result,
            "overall_similarity": _calculate_similarity(comparison_result),
            "recommendation": _get_practice_recommendation(comparison_result),
            "compared_at": datetime.now().isoformat()
        }
        
        logger.info(f"발음 비교 완료: {request.reference_word}")
        
        return PronunciationResponse(
            success=True,
            message="발음 비교가 완료되었습니다.",
            data=response_data
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"발음 비교 오류: {e}")
        raise HTTPException(status_code=500, detail=f"발음 비교 중 오류가 발생했습니다: {str(e)}")

# === 정보 조회 API ===

@app.get("/api/situations", tags=["Info"],
        summary="사용 가능한 대화 상황 조회",
        description="대화 연습에서 사용할 수 있는 모든 상황 목록을 조회합니다.")
async def get_available_situations():
    """사용 가능한 대화 상황 목록"""
    
    try:
        situations = conversation_ai_service.get_available_situations()
        
        # 각 상황별 시나리오 개수도 함께 반환
        situation_info = {}
        for situation in situations:
            scenarios = conversation_ai_service.conversation_scenarios.get(situation, {}).get('scenarios', [])
            scenario_count = len(scenarios)
            situation_info[situation] = {
                "name": situation.title(),
                "scenario_count": scenario_count,
                "description": f"{situation.title()} conversation practice"
            }
        
        return {
            "success": True,
            "situations": situation_info,
            "total_scenarios": sum(info["scenario_count"] for info in situation_info.values())
        }
        
    except Exception as e:
        logger.error(f"상황 목록 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=f"상황 목록 조회 중 오류: {str(e)}")

@app.get("/api/languages", tags=["Info"],
        summary="지원하는 언어 목록 (5개 언어)",
        description="시스템에서 지원하는 모든 언어 목록을 조회합니다.")
async def get_supported_languages():
    """지원하는 언어 목록 - 5개 언어"""
    
    try:
        stt_languages = stt_service.get_supported_languages()
        tts_languages = tts_service.get_supported_languages()
        
        # 5개 언어 통합 정보
        language_support = {
            "ko": {
                "name": "한국어",
                "native_name": "한국어",
                "stt_supported": "ko-KR" in stt_languages.values(),
                "tts_supported": "ko" in tts_languages.values(),
                "conversation_supported": True,
                "pronunciation_supported": True,
                "level_test_supported": True
            },
            "en": {
                "name": "English",
                "native_name": "English",
                "stt_supported": "en-US" in stt_languages.values(),
                "tts_supported": "en" in tts_languages.values(),
                "conversation_supported": True,
                "pronunciation_supported": True,
                "level_test_supported": True
            },
            "ja": {
                "name": "Japanese",
                "native_name": "日本語",
                "stt_supported": "ja-JP" in stt_languages.values(),
                "tts_supported": "ja" in tts_languages.values(),
                "conversation_supported": True,
                "pronunciation_supported": True,
                "level_test_supported": True
            },
            "zh": {
                "name": "Chinese",
                "native_name": "中文",
                "stt_supported": "zh-CN" in stt_languages.values(),
                "tts_supported": "zh" in tts_languages.values(),
                "conversation_supported": True,
                "pronunciation_supported": True,
                "level_test_supported": True
            },
            "fr": {
                "name": "French",
                "native_name": "Français",
                "stt_supported": "fr-FR" in stt_languages.values(),
                "tts_supported": "fr" in tts_languages.values(),
                "conversation_supported": True,
                "pronunciation_supported": True,
                "level_test_supported": True
            }
        }
        
        return {
            "success": True,
            "supported_languages": language_support,
            "total_languages": len(language_support),
            "fully_supported": ["ko", "en", "ja", "zh", "fr"],
            "default_language": "ko",
            "features_by_language": {
                lang: {
                    "conversation": info["conversation_supported"],
                    "speech_recognition": info["stt_supported"],
                    "text_to_speech": info["tts_supported"],
                    "pronunciation_analysis": info["pronunciation_supported"],
                    "level_testing": info["level_test_supported"]
                }
                for lang, info in language_support.items()
            }
        }
        
    except Exception as e:
        logger.error(f"언어 목록 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=f"언어 목록 조회 중 오류: {str(e)}")

# 언어별 시나리오 정보 API
@app.get("/api/scenarios/{language}", tags=["Info"],
        summary="언어별 시나리오 정보",
        description="특정 언어의 사용 가능한 시나리오 정보를 조회합니다.")
async def get_language_scenarios(language: str, SUPPORTED_LANGUAGES=None, LANGUAGE_NAMES=None):
    """언어별 시나리오 정보"""
    
    if language not in SUPPORTED_LANGUAGES:
        raise HTTPException(
            status_code=400,
            detail=f"지원하지 않는 언어: {language}. 지원 언어: {SUPPORTED_LANGUAGES}"
        )
    
    try:
        scenarios_info = {
            "language": language,
            "language_name": LANGUAGE_NAMES.get(language),
            "available_situations": ["airport", "restaurant", "hotel", "street"],
            "situation_details": {
                "airport": {
                    "title": {
                        "ko": "공항 체크인",
                        "en": "Airport Check-in",
                        "ja": "空港でのチェックイン", 
                        "zh": "机场值机",
                        "fr": "Enregistrement à l'aéroport"
                    }.get(language),
                    "description": "공항에서의 체크인 및 탑승 절차 연습"
                },
                "restaurant": {
                    "title": {
                        "ko": "레스토랑 주문",
                        "en": "Restaurant Ordering",
                        "ja": "レストランでの注文",
                        "zh": "餐厅点餐", 
                        "fr": "Commande au restaurant"
                    }.get(language),
                    "description": "레스토랑에서 주문하기 연습"
                },
                "hotel": {
                    "title": {
                        "ko": "호텔 체크인",
                        "en": "Hotel Check-in",
                        "ja": "ホテルでのチェックイン",
                        "zh": "酒店入住",
                        "fr": "Enregistrement à l'hôtel"
                    }.get(language),
                    "description": "호텔 체크인 및 서비스 이용 연습"
                },
                "street": {
                    "title": {
                        "ko": "길 찾기",
                        "en": "Asking for Directions", 
                        "ja": "道案内",
                        "zh": "问路",
                        "fr": "Demander son chemin"
                    }.get(language),
                    "description": "길 찾기 및 일상 대화 연습"
                }
            }
        }
        
        return {
            "success": True,
            "data": scenarios_info
        }
        
    except Exception as e:
        logger.error(f"언어별 시나리오 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/api/openai/status", tags=["System"],
        summary="OpenAI 서비스 상태",
        description="OpenAI GPT-4 서비스의 연결 상태를 확인합니다.")
async def get_openai_status():
    """OpenAI 서비스 상태 확인"""
    
    try:
        status = await conversation_ai_service.get_openai_status()
        
        return {
            "success": True,
            "openai_status": status,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"OpenAI 상태 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=f"OpenAI 상태 조회 중 오류: {str(e)}")

# === Voice Cloning API ===

@app.post("/api/voice/clone", tags=["Voice Cloning"],
         summary="사용자 음성 복제",
         description="사용자의 음성 샘플로 voice clone을 생성합니다.")
async def create_voice_clone(request: VoiceCloneRequest):
    """사용자 음성으로 voice clone 생성"""
    
    try:
        result = await voice_cloning_service.create_user_voice_clone(
            user_id=request.user_id,
            voice_sample_base64=request.voice_sample_base64,
            voice_name=request.voice_name
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Voice clone 생성 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/pronunciation/personalized-correction", tags=["Pronunciation"],
          summary="개인화된 발음 교정 (캐싱)",
          description="세션 ID를 기반으로 저장된 교정 음성을 가져오거나, 없으면 새로 생성합니다.")
async def generate_personalized_pronunciation(request: PersonalizedCorrectionRequest): # Depends(get_current_user) 삭제
    """세션 ID 기반으로 교정 음성 조회 또는 생성"""
    try:
        # 요청 본문에서 user_id를 직접 가져옵니다.
        user_id = request.user_id
        if not user_id:
            # 이 경우는 Pydantic 모델에서 필수로 지정했기 때문에 발생하지 않아야 합니다.
            raise HTTPException(status_code=400, detail="user_id가 필요합니다.")

        # 서비스 함수 호출 (user_id를 직접 전달)
        result = await pronunciation_service.get_or_create_corrected_audio(
            user_id=user_id,
            session_id=request.session_id
        )

        if result.get("success"):
            return {
                "success": True,
                "message": "교정 음성을 성공적으로 가져왔습니다.",
                "data": {
                    "corrected_audio_base64": result.get("corrected_audio_base64"),
                    "from_cache": result.get("cached", False)
                }
            }
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "교정 음성 처리 실패"))

    except Exception as e:
        logger.error(f"개인화 발음 교정 최종 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# === WebSocket 실시간 통신 ===

@app.websocket("/ws/conversation/{session_id}")
async def websocket_conversation(websocket: WebSocket, session_id: str):
    """실시간 대화 WebSocket (데이터 수집 포함)"""
    
    await websocket.accept()
    connected_clients[session_id] = websocket
    logger.info(f"WebSocket 연결: {session_id}")
    
    try:
        while True:
            # 클라이언트로부터 메시지 수신
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            message_type = message_data.get("type")
            
            if message_type == "text":
                # 텍스트 메시지 처리
                result = await conversation_ai_service.process_user_response(
                    session_id=session_id,
                    user_message=message_data["text"]
                )
                
                # TTS 음성 생성
                ai_audio = None
                try:
                    if result["success"] and result.get("ai_message") and not result.get("completed", False):
                        ai_audio = await tts_service.text_to_speech_base64(
                            text=result["ai_message"],
                            language="en"
                        )
                except Exception as tts_error:
                    logger.warning(f"WebSocket TTS 생성 실패: {tts_error}")
                
                # 응답 전송
                response = {
                    "type": "text_response",
                    "data": {
                        **result,
                        "ai_audio_base64": ai_audio,
                        "timestamp": datetime.now().isoformat()
                    }
                }
                
                await websocket.send_text(json.dumps(response))
                
            elif message_type == "voice":
                # 음성 메시지 처리
                try:
                    recognized_text = await stt_service.recognize_from_base64(
                        audio_base64=message_data["audio_base64"],
                        language=message_data.get("language", "en-US")
                    )
                    
                    if recognized_text:
                        # 인식된 텍스트로 대화 처리
                        result = await conversation_ai_service.process_user_response(
                            session_id=session_id,
                            user_message=recognized_text
                        )
                        
                        # 응답 음성 생성
                        ai_audio = None
                        try:
                            if result["success"] and result.get("ai_message") and not result.get("completed", False):
                                ai_audio = await tts_service.text_to_speech_base64(
                                    text=result["ai_message"],
                                    language="en"
                                )
                        except Exception as tts_error:
                            logger.warning(f"WebSocket 음성 응답 TTS 생성 실패: {tts_error}")
                        
                        response = {
                            "type": "voice_response",
                            "data": {
                                **result,
                                "recognized_text": recognized_text,
                                "ai_audio_base64": ai_audio,
                                "timestamp": datetime.now().isoformat()
                            }
                        }
                        
                        await websocket.send_text(json.dumps(response))
                    else:
                        # 음성 인식 실패
                        error_response = {
                            "type": "error",
                            "data": {
                                "message": "음성 인식에 실패했습니다.",
                                "timestamp": datetime.now().isoformat()
                            }
                        }
                        await websocket.send_text(json.dumps(error_response))
                except Exception as stt_error:
                    logger.error(f"WebSocket 음성 처리 오류: {stt_error}")
                    error_response = {
                        "type": "error",
                        "data": {
                            "message": f"음성 처리 중 오류: {str(stt_error)}",
                            "timestamp": datetime.now().isoformat()
                        }
                    }
                    await websocket.send_text(json.dumps(error_response))
            
            elif message_type == "ping":
                # 연결 상태 확인
                pong_response = {
                    "type": "pong",
                    "data": {
                        "timestamp": datetime.now().isoformat()
                    }
                }
                await websocket.send_text(json.dumps(pong_response))
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket 연결 해제: {session_id}")
        if session_id in connected_clients:
            del connected_clients[session_id]
    except Exception as e:
        logger.error(f"WebSocket 오류: {e}")
        if session_id in connected_clients:
            del connected_clients[session_id]

# === 예외 처리 ===

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """HTTP 예외 처리"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.detail,
            "timestamp": datetime.now().isoformat()
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """일반 예외 처리"""
    logger.error(f"예상치 못한 오류: {exc}")
    import traceback
    logger.error(f"상세 오류: {traceback.format_exc()}")
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "서버 내부 오류가 발생했습니다.",
            "timestamp": datetime.now().isoformat()
        }
    )

@app.post("/api/grammar/start-session", tags=["Grammar"], summary="Start Grammar Practice Session")
async def start_grammar_session(request: GrammarStartRequest):
    """
    Starts a new grammar practice session and returns the first question.
    """
    try:
        result = await grammar_practice_service.start_grammar_session(
            user_id=request.user_id,
            language=request.language,
            level=request.level
        )
        if result["success"]:
            return result
        else:
            raise HTTPException(status_code=400, detail=result.get("error", "Failed to start session."))
    except Exception as e:
        logger.error(f"Error starting grammar session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/grammar/submit-answer", tags=["Grammar"], summary="Submit Grammar Answer")
async def submit_grammar_answer(request: GrammarAnswerRequest):
    """
    Submits a grammar answer, gets feedback, and the next question.
    """
    try:
        result = await grammar_practice_service.submit_grammar_answer(
            session_id=request.session_id,
            question_id=request.question_id,
            user_answer=request.answer
        )
        if result["success"]:
            return result
        else:
            raise HTTPException(status_code=400, detail=result.get("error", "Failed to submit answer."))
    except Exception as e:
        logger.error(f"Error submitting grammar answer: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/grammar/analyze-voice")
async def analyze_grammar_from_voice(request: GrammarVoiceRequest):
    try:
        # 1. 음성을 텍스트로 변환 (STT) - 변경 없음
        transcribed_text = await stt_service.recognize_from_base64(
            audio_base64=request.audio_base64,
            language="en-US"
        )
        if not transcribed_text:
            return {"success": False, "error": "음성을 인식할 수 없습니다."}

        # 2. 텍스트의 문법 분석 및 교정 (OpenAI) - 변경 없음
        feedback_data = await openai_service.get_grammar_feedback(
            user_message=transcribed_text,
            language=request.language,
            level=request.level
        )
        corrected_text = feedback_data.get("corrected_text")
        if not corrected_text:
            return {"success": False, "error": "문법 분석에 실패했습니다."}

        # 3. ▼▼▼ [삭제] 교정된 텍스트를 음성으로 변환하는 로직 전체 삭제 ▼▼▼
        # corrected_audio_base64 = await tts_service.text_to_speech_base64(...)

        # 4. ▼▼▼ [수정] 최종 결과에서 오디오 부분 삭제 ▼▼▼
        return {
            "success": True,
            "data": {
                "transcribed_text": transcribed_text,
                "corrected_text": corrected_text,
                "grammar_feedback": feedback_data.get("grammar_feedback", []),
                "vocabulary_suggestions": feedback_data.get("vocabulary_suggestions", [])
                # "corrected_audio_base64" 키 삭제
            }
        }

    except Exception as e:
        logger.error(f"음성 문법 분석 중 오류: {e}")
        return {"success": False, "error": str(e)}


# === 서버 실행 ===

if __name__ == "__main__":
    logger.info("🚀 AI Language Learning API 서버 시작! (데이터 수집 + Fine-tuning + Swagger UI)")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
