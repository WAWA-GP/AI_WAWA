# app/main.py
# FastAPI 메인 서버 - AI 언어 학습 앱 (OpenAI 통합) with Swagger UI

import os
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, Dict, List
import asyncio
import json
import logging
import uvicorn
from datetime import datetime, timedelta
from dotenv import load_dotenv
from services.pronunciation_analysis_service import pronunciation_service
from supabase import create_client
load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

supabase = create_client(url, key)

# 서비스 임포트
try:
    from services.conversation_ai_service import conversation_ai_service
    from services.speech_recognition_service import stt_service
    from services.text_to_speech_service import tts_service
    from services.openai_service import openai_service
    from services.level_test_service import level_test_service
    from services.voice_cloning_service import voice_cloning_service
except ImportError:
    print("⚠️ 서비스 모듈을 찾을 수 없습니다. 경로를 확인해주세요.")
    import sys
    sys.exit(1)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# FastAPI 앱 생성 with Swagger 설정
app = FastAPI(
    title="AI Language Learning API",
    description="""
    AI 기반 언어 학습 대화 시스템
    
    ## 주요 기능
    * **레벨 테스트**: 적응형 언어 레벨 평가 (CEFR 표준)
    * **대화 연습**: OpenAI GPT-4 기반 실시간 대화
    * **발음 분석**: 음성 억양 및 발음 평가
    * **개인화**: 사용자별 맞춤형 학습 경로
    
    ## 지원 언어
    한국어, 영어, 일본어, 중국어
    
    ## 사용 방법
    1. `/api/user/initialize`로 사용자 초기화 및 레벨 테스트 시작
    2. `/api/level-test/answer`로 레벨 테스트 완료
    3. `/api/conversation/start`로 대화 연습 시작
    4. `/api/pronunciation/analyze`로 발음 분석
    """,
    version="2.0.0",
    contact={
        "name": "Language Learning Team",
        "email": "support@example.com",
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT",
    },
    docs_url="/docs",      # Swagger UI 경로
    redoc_url=None,        # ReDoc 비활성화
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

# === Pydantic 모델들 (Pydantic V2 호환) ===

class ConversationStartRequest(BaseModel):
    user_id: str = Field(..., description="사용자 고유 ID")
    situation: str = Field(..., description="대화 상황 (airport, restaurant, hotel, street)")
    difficulty: str = Field("beginner", description="난이도 (beginner, intermediate, advanced)")
    language: str = Field("en", description="언어 코드 (ko, en, ja, zh)")
    mode: str = Field("auto", description="대화 모드 (scenario, openai, hybrid, auto)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user123",
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
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "session_12345",
                "message": "I would like to order a coffee, please.",
                "language": "en"
            }
        }

class VoiceMessageRequest(BaseModel):
    session_id: str = Field(..., description="세션 ID")
    audio_base64: str = Field(..., description="Base64 인코딩된 오디오 데이터")
    language: str = Field("en", description="언어 코드")
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "session_12345",
                "audio_base64": "UklGRnoGAABXQVZFZm10IBAAAAABAAEA...",
                "language": "en"
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
                    "ai_message": "안녕하세요! 레스토랑 대화를 연습해봅시다."
                },
                "error": None
            }
        }

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
    
    class Config:
        json_schema_extra = {
            "example": {
                "audio_base64": "UklGRnoGAABXQVZFZm10IBAAAAABAAEA...",
                "target_text": "Hello, how are you?",
                "user_level": "B1",
                "language": "en"
            }
        }

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
    user_id: str = Field(..., description="사용자 고유 ID")
    target_text: str = Field(..., description="교정할 대상 텍스트")
    user_audio_base64: str = Field(..., description="사용자 발음 오디오 (Base64)")
    user_level: str = Field("B1", description="사용자 레벨 (A1-C2)")
    language: str = Field("en", description="언어 코드")
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user123",
                "target_text": "Can I book a flight to LA now?",
                "user_audio_base64": "UklGRnoGAABXQVZFZm10IBAAAAABAAEA...",
                "user_level": "B1",
                "language": "en"
            }
        }

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

def analyze_response_patterns(responses: List[Dict]) -> Dict:
    """응답 패턴 분석"""
    if not responses:
        return {}
    
    correct_answers = sum(1 for r in responses if r.get("correct", False))
    total_answers = len(responses)
    
    # 스킬별 정답률
    skill_accuracy = {}
    for response in responses:
        skill = response.get("skill", "unknown")
        if skill not in skill_accuracy:
            skill_accuracy[skill] = {"correct": 0, "total": 0}
        
        skill_accuracy[skill]["total"] += 1
        if response.get("correct", False):
            skill_accuracy[skill]["correct"] += 1
    
    # 정답률 계산
    for skill in skill_accuracy:
        total = skill_accuracy[skill]["total"]
        correct = skill_accuracy[skill]["correct"]
        skill_accuracy[skill]["accuracy"] = round(correct / total * 100, 1) if total > 0 else 0
    
    return {
        "overall_accuracy": round(correct_answers / total_answers * 100, 1),
        "skill_accuracy": skill_accuracy,
        "consistency": calculate_response_consistency(responses)
    }

def analyze_response_times(responses: List[Dict]) -> Dict:
    """응답 시간 분석 (실제로는 타임스탬프 기반)"""
    # 실제 구현에서는 각 응답의 시간 정보를 사용
    return {
        "average_time": "45 seconds",
        "fastest_response": "12 seconds", 
        "slowest_response": "2 minutes",
        "time_trend": "improving"  # getting faster/slower/consistent
    }

def analyze_difficulty_progression(responses: List[Dict]) -> Dict:
    """난이도 진행 분석"""
    if not responses:
        return {}
    
    # 레벨별 응답 분포
    level_distribution = {}
    for response in responses:
        level = response.get("level", "unknown")
        level_distribution[level] = level_distribution.get(level, 0) + 1
    
    return {
        "level_distribution": level_distribution,
        "adaptive_progression": "successful",  # successful/struggled/inconsistent
        "final_confidence": "high"  # high/medium/low
    }

def calculate_response_consistency(responses: List[Dict]) -> str:
    """응답 일관성 계산"""
    if len(responses) < 3:
        return "insufficient_data"
    
    scores = [r.get("score", 0) for r in responses]
    variance = sum((score - sum(scores)/len(scores))**2 for score in scores) / len(scores)
    
    if variance < 100:
        return "highly_consistent"
    elif variance < 400:
        return "moderately_consistent" 
    else:
        return "inconsistent"

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

def _get_pronunciation_tips(word: str, reference_info: Dict) -> List[str]:
    """발음 팁 생성"""
    
    tips = []
    
    if reference_info:
        syllables = reference_info.get('expected_syllables', 1)
        
        if syllables == 1:
            tips.append("단음절 단어이므로 명확하게 발음하세요.")
        elif syllables >= 3:
            tips.append("다음절 단어이므로 강세 위치에 주의하세요.")
        
        stress_pattern = reference_info.get('stress_pattern', [])
        if stress_pattern and len(stress_pattern) > 1:
            stress_pos = stress_pattern.index(1) + 1 if 1 in stress_pattern else 1
            tips.append(f"{stress_pos}번째 음절에 강세를 두세요.")
    
    # 단어별 특별 팁
    word_tips = {
        'water': "미국식 발음에서는 't'를 'd'처럼 발음합니다.",
        'better': "두 번째 'e'는 약하게 발음하세요.",
        'computer': "com-PU-ter로 두 번째 음절에 강세를 두세요.",
        'important': "im-POR-tant로 두 번째 음절에 강세를 두세요."
    }
    
    if word.lower() in word_tips:
        tips.append(word_tips[word.lower()])
    
    if not tips:
        tips.append("천천히 명확하게 발음해보세요.")
    
    return tips

def _generate_practice_phrases(word: str) -> List[str]:
    """연습 문장 생성"""
    
    phrases = [
        f"I can say '{word}' clearly.",
        f"The word '{word}' is important.",
        f"Let me practice '{word}' again."
    ]
    
    # 단어별 특별 문장들
    word_phrases = {
        'water': [
            "I drink water every day.",
            "The water is very cold.",
            "Can I have some water please?"
        ],
        'computer': [
            "I use my computer for work.",
            "The computer is very fast.",
            "My new computer is great."
        ],
        'important': [
            "This is very important.",
            "Education is important for everyone.",
            "It's important to practice daily."
        ]
    }
    
    if word.lower() in word_phrases:
        return word_phrases[word.lower()]
    
    return phrases

def _assess_difficulty(word: str, reference_info: Dict) -> str:
    """단어 발음 난이도 평가"""
    
    if not reference_info:
        return "medium"
    
    syllables = reference_info.get('expected_syllables', 1)
    phonemes = reference_info.get('phonemes', [])
    
    # 난이도 점수 계산
    difficulty_score = 0
    
    # 음절 수에 따른 점수
    if syllables >= 4:
        difficulty_score += 3
    elif syllables == 3:
        difficulty_score += 2
    elif syllables == 2:
        difficulty_score += 1
    
    # 어려운 음소 확인
    difficult_phonemes = ['TH', 'R', 'L', 'ZH', 'NG']
    for phoneme in phonemes:
        if phoneme in difficult_phonemes:
            difficulty_score += 1
    
    # 난이도 결정
    if difficulty_score <= 1:
        return "easy"
    elif difficulty_score <= 3:
        return "medium"
    else:
        return "hard"

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
        "message": "AI Language Learning API with OpenAI + Level Assessment",
        "status": "running",
        "version": "2.0.0",
        "features": [
            "scenario_conversations", 
            "openai_gpt4", 
            "voice_support", 
            "hybrid_mode",
            "adaptive_level_testing",
            "personalized_learning_paths"
        ],
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health", tags=["System"], summary="서비스 상태 체크")
async def health_check():
    """
    모든 서비스의 상태를 확인합니다.
    
    각 서비스(대화 AI, 음성 인식, TTS, OpenAI, 레벨 테스트)의 상태를 점검하고
    전체적인 시스템 건강도를 반환합니다.
    """
    
    # 각 서비스 상태 확인
    services_status = {
        "conversation_ai": True,
        "speech_recognition": True,
        "text_to_speech": True,
        "openai_gpt4": True,
        "level_test": True
    }
    
    try:
        # 대화 AI 서비스 테스트
        situations = conversation_ai_service.get_available_situations()
        services_status["conversation_ai"] = len(situations) > 0
        
        # STT 서비스 테스트
        supported_langs = stt_service.get_supported_languages()
        services_status["speech_recognition"] = len(supported_langs) > 0
        
        # TTS 서비스 테스트
        tts_langs = tts_service.get_supported_languages()
        services_status["text_to_speech"] = len(tts_langs) > 0
        
        # OpenAI 서비스 테스트
        openai_status = await openai_service.test_connection()
        services_status["openai_gpt4"] = openai_status.get("connected", False)
        
        # 레벨 테스트 서비스 테스트
        services_status["level_test"] = level_test_service is not None
        
    except Exception as e:
        logger.error(f"서비스 상태 확인 오류: {e}")
        services_status["error"] = str(e)
    
    all_healthy = all(status for key, status in services_status.items() if key != "error")
    
    return {
        "healthy": all_healthy,
        "services": services_status,
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

@app.post("/api/level-test/start", tags=["Level Test"],
         summary="레벨 테스트 시작",
         description="사용자의 언어 실력을 평가하는 적응형 레벨 테스트를 시작합니다.")
async def start_level_test(request: LevelTestStartRequest):
    """사용자 레벨 테스트 시작"""
    try:
        logger.info(f"레벨 테스트 시작 요청: {request.user_id} - {request.language}")
        
        result = await level_test_service.start_level_test(
            user_id=request.user_id,
            language=request.language
        )
        
        if result["success"]:
            return {
                "success": True,
                "message": "레벨 테스트가 시작되었습니다.",
                "data": result
            }
        else:
            raise HTTPException(status_code=400, detail=result["error"])
            
    except Exception as e:
        logger.error(f"레벨 테스트 시작 오류: {e}")
        raise HTTPException(status_code=500, detail=f"레벨 테스트 시작 중 오류: {str(e)}")

@app.post("/api/level-test/answer", tags=["Level Test"],
         summary="레벨 테스트 답변 제출",
         description="레벨 테스트 문제에 대한 답변을 제출하고 다음 문제 또는 결과를 받습니다.")
async def submit_test_answer(request: LevelTestAnswerRequest):
    """레벨 테스트 답변 제출"""
    try:
        logger.info(f"레벨 테스트 답변 제출: {request.session_id} - {request.question_id}")
        
        result = await level_test_service.submit_answer(
            session_id=request.session_id,
            question_id=request.question_id,
            answer=request.answer
        )
        
        if result["success"]:
            return {
                "success": True,
                "message": "답변이 처리되었습니다.",
                "data": result
            }
        else:
            raise HTTPException(status_code=400, detail=result["error"])
            
    except Exception as e:
        logger.error(f"답변 처리 오류: {e}")
        raise HTTPException(status_code=500, detail=f"답변 처리 중 오류: {str(e)}")

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
            "results": results,
            "detailed_analysis": {
                "response_patterns": analyze_response_patterns(session["responses"]),
                "time_analysis": analyze_response_times(session["responses"]),
                "difficulty_progression": analyze_difficulty_progression(session["responses"])
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"결과 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=f"결과 조회 중 오류: {str(e)}")

@app.post("/api/user/complete-assessment", tags=["User"],
         summary="레벨 평가 완료",
         description="레벨 테스트 완료 후 개인화된 학습 경로를 제공합니다.")
async def complete_assessment(
    user_id: str = Query(..., description="사용자 ID"),
    session_id: str = Query(..., description="테스트 세션 ID")
):
    """레벨 테스트 완료 후 개인화된 학습 경로 제공"""
    try:
        # 레벨 테스트 결과 조회
        session_status = level_test_service.get_session_status(session_id)
        
        if not session_status.get("exists") or not session_status.get("completed"):
            raise HTTPException(status_code=400, detail="완료되지 않은 테스트입니다.")
        
        # 세션에서 최종 결과 가져오기
        session = level_test_service.active_sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
        
        # 사용자 프로필 생성
        final_result = session.get("final_result", {})
        user_level = final_result.get("final_level", "A2")
        weak_areas = final_result.get("areas_to_improve", [])
        
        # 개인화된 학습 경로 생성
        learning_path = await generate_personalized_learning_path(user_level, weak_areas)
        
        # 사용자 프로필 저장 (실제로는 데이터베이스에 저장)
        user_profile = {
            "user_id": user_id,
            "assessed_level": user_level,
            "skill_breakdown": final_result.get("skill_breakdown", {}),
            "strengths": final_result.get("strengths", []),
            "areas_to_improve": weak_areas,
            "learning_path": learning_path,
            "assessment_date": datetime.now().isoformat(),
            "recommended_daily_time": "20-30 minutes",
            "next_assessment_due": (datetime.now() + timedelta(days=30)).isoformat()
        }
        
        logger.info(f"사용자 평가 완료: {user_id} - 레벨: {user_level}")
        
        return {
            "success": True,
            "message": f"축하합니다! 당신의 레벨은 {user_level}입니다.",
            "data": {
                "user_profile": user_profile,
                "assessment_results": final_result,
                "first_lesson": await get_first_lesson_for_level(user_level, weak_areas),
                "learning_plan": {
                    "daily_goals": generate_daily_goals(user_level),
                    "weekly_plan": generate_weekly_plan(user_level, weak_areas),
                    "milestone_targets": generate_milestones(user_level)
                }
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"평가 완료 처리 오류: {e}")
        raise HTTPException(status_code=500, detail=f"평가 완료 처리 중 오류: {str(e)}")

# === 대화 관리 API ===

@app.post("/api/conversation/start", tags=["Conversation"],
         summary="대화 세션 시작",
         description="새로운 대화 세션을 시작합니다. OpenAI GPT-4 또는 시나리오 기반 대화를 선택할 수 있습니다.",
         response_model=ConversationResponse)
async def start_conversation(request: ConversationStartRequest):
    """새로운 대화 세션 시작 (OpenAI 지원)"""
    
    try:
        logger.info(f"대화 시작 요청: {request.user_id} - {request.situation} (모드: {request.mode})")
        
        # 세션 ID 생성
        session_id = f"{request.user_id}_{request.situation}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # 향상된 대화 서비스로 시작
        result = await conversation_ai_service.start_conversation(
            session_id=session_id,
            situation=request.situation,
            difficulty=request.difficulty,
            language=request.language,
            mode=request.mode
        )
        
        if result["success"]:
            response_data = {
                "session_id": session_id,
                "situation": request.situation,
                "difficulty": request.difficulty,
                "language": request.language,
                "mode": result["mode"],
                "scenario_title": result.get("scenario_title", f"{request.situation.title()} Conversation"),
                "ai_message": result["first_message"],
                "features": result.get("features", []),
                "scenario_context": result.get("scenario_context", {}),
                "available_situations": conversation_ai_service.get_available_situations()
            }
            
            # 시나리오 모드일 때만 expected_responses 추가
            if "expected_responses" in result:
                response_data["expected_responses"] = result["expected_responses"]
            
            logger.info(f"대화 세션 시작 성공: {session_id} (모드: {result['mode']})")
            
            return ConversationResponse(
                success=True,
                message=f"대화 세션이 시작되었습니다. (모드: {result['mode']})",
                data=response_data
            )
        else:
            logger.warning(f"대화 시작 실패: {result['error']}")
            raise HTTPException(status_code=400, detail=result["error"])
            
    except Exception as e:
        logger.error(f"대화 시작 오류: {e}")
        raise HTTPException(status_code=500, detail=f"대화 시작 중 오류: {str(e)}")

@app.post("/api/conversation/text", tags=["Conversation"],
         summary="텍스트 메시지 전송",
         description="대화 세션에 텍스트 메시지를 전송하고 AI 응답을 받습니다.",
         response_model=ConversationResponse)
async def send_text_message(request: TextMessageRequest):
    """텍스트 메시지 처리 (OpenAI 지원)"""
    
    try:
        logger.info(f"텍스트 메시지: {request.session_id} - {request.message[:50]}...")
        
        # 입력 검증
        if not request.message or request.message.strip() == "":
            raise HTTPException(status_code=400, detail="메시지가 비어있습니다.")
        
        # 향상된 대화 AI 처리
        result = await conversation_ai_service.process_user_response(
            session_id=request.session_id,
            user_message=request.message
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
                "completed": completed
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
        
        if not recognized_text:
            raise HTTPException(status_code=400, detail="음성 인식에 실패했습니다.")
        
        logger.info(f"음성 인식 결과: {recognized_text}")
        
        # 텍스트 메시지로 처리
        text_request = TextMessageRequest(
            session_id=request.session_id,
            message=recognized_text,
            language=request.language
        )
        
        # 기존 텍스트 처리 로직 재사용
        response = await send_text_message(text_request)
        
        # 음성 인식 결과 추가
        if response.data:
            response.data["recognized_text"] = recognized_text
            response.data["original_audio"] = True
        
        return response
        
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
                "last_activity": session_status.get("last_activity", datetime.now().isoformat())
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
        # 향상된 세션 종료
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

# === 발음 분석 API ===

@app.post("/api/pronunciation/analyze", tags=["Pronunciation"],
         summary="음성 억양 분석",
         description="사용자의 음성을 분석하여 발음, 억양, 리듬 등을 평가합니다.",
         response_model=PronunciationResponse)
async def analyze_pronunciation(request: PronunciationAnalysisRequest):
    """음성 억양 분석"""
    
    try:
        logger.info(f"억양 분석 요청: {len(request.target_text)} 글자, 레벨: {request.user_level}")
        
        # 입력 검증
        if not request.audio_base64:
            raise HTTPException(status_code=400, detail="음성 데이터가 없습니다.")
        
        if not request.target_text:
            raise HTTPException(status_code=400, detail="대상 텍스트가 없습니다.")
        
        # 억양 분석 수행
        result = await pronunciation_service.analyze_pronunciation_from_base64(
            audio_base64=request.audio_base64,
            target_text=request.target_text,
            user_level=request.user_level
        )
        
        # 응답 데이터 구성
        response_data = {
            "analysis_id": f"pronunciation_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "target_text": request.target_text,
            "user_level": request.user_level,
            "scores": {
                "overall": result.overall_score,
                "pitch": result.pitch_score,
                "rhythm": result.rhythm_score,
                "stress": result.stress_score,
                "fluency": result.fluency_score
            },
            "grade": _get_grade_from_score(result.overall_score),
            "feedback": {
                "detailed": result.detailed_feedback,
                "suggestions": result.suggestions,
                "phoneme_scores": result.phoneme_scores
            },
            "improvement_priority": _get_improvement_priority(result),
            "analyzed_at": datetime.now().isoformat()
        }
        
        logger.info(f"억양 분석 완료: 전체 점수 {result.overall_score:.1f}")
        
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

@app.get("/api/pronunciation/reference/{word}", tags=["Pronunciation"],
        summary="표준 발음 정보 조회",
        description="특정 단어의 표준 발음 정보를 조회합니다.")
async def get_reference_pronunciation(word: str):
    """표준 발음 정보 조회"""
    
    try:
        logger.info(f"표준 발음 조회: {word}")
        
        # 표준 발음 정보 가져오기
        reference_info = await pronunciation_service.get_reference_pronunciation(word)
        
        if reference_info:
            response_data = {
                "word": word,
                "reference_info": reference_info,
                "pronunciation_tips": _get_pronunciation_tips(word, reference_info),
                "practice_phrases": _generate_practice_phrases(word),
                "difficulty_level": _assess_difficulty(word, reference_info),
                "retrieved_at": datetime.now().isoformat()
            }
            
            return {
                "success": True,
                "message": f"'{word}'의 표준 발음 정보입니다.",
                "data": response_data
            }
        else:
            return {
                "success": False,
                "message": f"'{word}'의 발음 정보를 찾을 수 없습니다.",
                "data": None
            }
            
    except Exception as e:
        logger.error(f"표준 발음 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=f"표준 발음 조회 중 오류가 발생했습니다: {str(e)}")

@app.get("/api/pronunciation/features", tags=["Pronunciation"],
        summary="발음 분석 기능 정보",
        description="지원하는 발음 분석 기능 목록을 조회합니다.")
async def get_pronunciation_features():
    """발음 분석 기능 정보"""
    
    try:
        features = pronunciation_service.get_supported_features()
        
        return {
            "success": True,
            "message": "발음 분석 기능 정보입니다.",
            "data": {
                "supported_features": features,
                "api_endpoints": {
                    "analyze": "/api/pronunciation/analyze",
                    "compare": "/api/pronunciation/compare", 
                    "reference": "/api/pronunciation/reference/{word}",
                    "features": "/api/pronunciation/features"
                },
                "usage_examples": {
                    "analyze": {
                        "description": "음성 파일의 억양을 분석합니다",
                        "required_fields": ["audio_base64", "target_text"],
                        "optional_fields": ["user_level", "language"]
                    },
                    "compare": {
                        "description": "사용자 발음과 표준 발음을 비교합니다",
                        "required_fields": ["audio_base64", "reference_word"],
                        "optional_fields": ["user_level", "language"]
                    }
                },
                "data_sources": [
                    "CMU Pronouncing Dictionary (무료)",
                    "Forvo API (선택적)",
                    "음성학 규칙 기반 패턴",
                    "Praat 음성 분석 라이브러리"
                ]
            }
        }
        
    except Exception as e:
        logger.error(f"기능 정보 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=f"기능 정보 조회 중 오류가 발생했습니다: {str(e)}")

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

@app.post("/api/pronunciation/personalized-correction", tags=["Voice Cloning"],
         summary="개인화된 발음 교정",
         description="사용자의 목소리로 완벽한 발음 교정 음성을 생성합니다.")
async def generate_personalized_pronunciation(request: PersonalizedCorrectionRequest):
    """사용자 목소리로 완벽한 발음 교정 음성 생성"""
    
    try:
        # 1. 먼저 사용자의 발음 분석
        pronunciation_analysis = await pronunciation_service.analyze_pronunciation_from_base64(
            audio_base64=request.user_audio_base64,
            target_text=request.target_text,
            user_level=request.user_level
        )
        
        # 2. 분석 결과를 딕셔너리로 변환
        analysis_dict = {
            "overall_score": pronunciation_analysis.overall_score,
            "pitch_score": pronunciation_analysis.pitch_score,
            "rhythm_score": pronunciation_analysis.rhythm_score,
            "stress_score": pronunciation_analysis.stress_score,
            "fluency_score": pronunciation_analysis.fluency_score,
            "detailed_feedback": pronunciation_analysis.detailed_feedback,
            "suggestions": pronunciation_analysis.suggestions
        }
        
        # 3. 사용자 음색으로 교정된 발음 생성
        correction_result = await voice_cloning_service.generate_corrected_pronunciation(
            user_id=request.user_id,
            target_text=request.target_text,
            pronunciation_analysis=analysis_dict,
            language=request.language
        )
        
        if correction_result["success"]:
            return {
                "success": True,
                "message": "개인화된 발음 교정이 완성되었습니다.",
                "data": {
                    "original_analysis": analysis_dict,
                    "corrected_audio_base64": correction_result["corrected_audio_base64"],
                    "original_text": request.target_text,
                    "corrected_text": correction_result.get("corrected_text"),
                    "corrections_applied": correction_result.get("corrections_applied", []),
                    "improvement_tips": pronunciation_analysis.suggestions
                }
            }
        else:
            return {
                "success": False,
                "error": correction_result.get("error", "교정 음성 생성 실패"),
                "original_analysis": analysis_dict
            }
        
    except Exception as e:
        logger.error(f"개인화 발음 교정 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/voice/{user_id}/info", tags=["Voice Cloning"],
        summary="사용자 음성 정보 조회",
        description="사용자의 voice clone 정보를 조회합니다.")
async def get_user_voice_info(user_id: str):
    """사용자 voice clone 정보 조회"""
    
    try:
        voice_info = await voice_cloning_service.get_user_voice_info(user_id)
        return voice_info
        
    except Exception as e:
        logger.error(f"Voice 정보 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/voice/{user_id}", tags=["Voice Cloning"],
           summary="사용자 음성 삭제",
           description="사용자의 voice clone을 삭제합니다.")
async def delete_user_voice(user_id: str):
    """사용자 voice clone 삭제"""
    
    try:
        result = await voice_cloning_service.delete_user_voice(user_id)
        return result
        
    except Exception as e:
        logger.error(f"Voice 삭제 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
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
        summary="지원하는 언어 목록",
        description="시스템에서 지원하는 모든 언어 목록을 조회합니다.")
async def get_supported_languages():
    """지원하는 언어 목록"""
    
    try:
        stt_languages = stt_service.get_supported_languages()
        tts_languages = tts_service.get_supported_languages()
        
        return {
            "success": True,
            "stt_languages": stt_languages,
            "tts_languages": tts_languages,
            "common_languages": ["korean", "english", "japanese", "chinese"]
        }
        
    except Exception as e:
        logger.error(f"언어 목록 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=f"언어 목록 조회 중 오류: {str(e)}")

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

# === WebSocket 실시간 통신 ===

@app.websocket("/ws/conversation/{session_id}")
async def websocket_conversation(websocket: WebSocket, session_id: str):
    """실시간 대화 WebSocket (OpenAI 지원)"""
    
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

# === 서버 실행 ===

if __name__ == "__main__":
    logger.info("🚀 AI Language Learning API 서버 시작! (OpenAI GPT-4 + Level Assessment + Swagger UI)")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )