# app/main.py
# FastAPI 메인 서버 - AI 언어 학습 앱 (OpenAI 통합)

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict, List
import asyncio
import json
import logging
import uvicorn
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

# 서비스 임포트
try:
    from services.conversation_ai_service import conversation_ai_service
    from services.speech_recognition_service import stt_service
    from services.text_to_speech_service import tts_service
    from services.openai_service import openai_service
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

# FastAPI 앱 생성
app = FastAPI(
    title="AI Language Learning API",
    description="AI 기반 언어 학습 대화 시스템 - OpenAI GPT-4 지원",
    version="1.5.0"
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

# === Pydantic 모델들 ===

class ConversationStartRequest(BaseModel):
    user_id: str
    situation: str  # airport, restaurant, hotel, street
    difficulty: str = "beginner"  # beginner, intermediate, advanced
    language: str = "en"  # ko, en, ja, zh
    mode: str = "auto"  # scenario, openai, hybrid, auto

class TextMessageRequest(BaseModel):
    session_id: str
    message: str
    language: str = "en"

class VoiceMessageRequest(BaseModel):
    session_id: str
    audio_base64: str
    language: str = "en"

class ConversationResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict] = None
    error: Optional[str] = None

# === 기본 라우트 ===

@app.get("/")
async def root():
    """API 상태 확인"""
    return {
        "message": "AI Language Learning API with OpenAI",
        "status": "running",
        "version": "1.5.0",
        "features": ["scenario_conversations", "openai_gpt4", "voice_support", "hybrid_mode"],
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health")
async def health_check():
    """서비스 상태 체크"""
    
    # 각 서비스 상태 확인
    services_status = {
        "conversation_ai": True,
        "speech_recognition": True,
        "text_to_speech": True,
        "openai_gpt4": True
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
        
    except Exception as e:
        logger.error(f"서비스 상태 확인 오류: {e}")
        services_status["error"] = str(e)
    
    all_healthy = all(status for key, status in services_status.items() if key != "error")
    
    return {
        "healthy": all_healthy,
        "services": services_status,
        "timestamp": datetime.now().isoformat()
    }

# === 대화 관리 API ===

@app.post("/api/conversation/start", response_model=ConversationResponse)
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

@app.post("/api/conversation/text", response_model=ConversationResponse)
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

@app.post("/api/conversation/voice", response_model=ConversationResponse)
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

@app.get("/api/conversation/{session_id}/status")
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

@app.delete("/api/conversation/{session_id}")
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

# === 정보 조회 API ===

@app.get("/api/situations")
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

@app.get("/api/languages")
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

@app.get("/api/openai/status")
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
    logger.info("🚀 AI Language Learning API 서버 시작! (OpenAI GPT-4 지원)")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )