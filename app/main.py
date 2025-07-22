"""
FastAPI 메인 애플리케이션
app/main.py
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
from datetime import datetime
import logging

# 로컬 임포트
from .config import settings, validate_settings

# 로깅 설정
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# FastAPI 앱 생성
app = FastAPI(
    title=settings.app_name,
    description="다국어 실시간 대화 학습을 위한 AI 백엔드 서비스",
    version=settings.app_version,
    debug=settings.debug
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# 글로벌 변수 (나중에 의존성 주입으로 개선)
conversation_sessions = {}

@app.on_event("startup")
async def startup_event():
    """앱 시작시 초기화"""
    logger.info(f"🚀 {settings.app_name} 시작 중...")
    logger.info(f"환경: {settings.environment}")
    logger.info(f"디버그 모드: {settings.debug}")
    
    # 설정 검증
    if not validate_settings():
        logger.error("❌ 설정 오류로 인해 서버를 시작할 수 없습니다.")
        exit(1)
    
    logger.info("✅ 서버 초기화 완료!")

@app.on_event("shutdown")
async def shutdown_event():
    """앱 종료시 정리"""
    logger.info("🛑 서버 종료 중...")
    logger.info("✅ 서버 종료 완료")

# 기본 라우트들
@app.get("/")
async def root():
    """헬스 체크 및 API 정보"""
    return {
        "app_name": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "message": "Language Learning AI API is running! 🚀"
    }

@app.get("/health")
async def health_check():
    """상세 헬스 체크"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "uptime": "계산 중...",  # 나중에 실제 업타임 계산
        "environment": settings.environment,
        "debug": settings.debug
    }

@app.get("/api/info")
async def api_info():
    """API 정보 및 지원 기능"""
    return {
        "app_name": settings.app_name,
        "version": settings.app_version,
        "supported_languages": settings.supported_languages,
        "default_language": settings.default_language,
        "features": [
            "실시간 대화",
            "음성 인식 (STT)",
            "음성 합성 (TTS)", 
            "문법 검사",
            "발음 평가",
            "학습 진도 추적"
        ],
        "endpoints": {
            "conversation": "/api/conversation/*",
            "speech": "/api/speech/*",
            "learning": "/api/learning/*"
        }
    }

# 간단한 테스트 엔드포인트
@app.post("/api/test/echo")
async def echo_test(message: dict):
    """메시지 에코 테스트"""
    return {
        "echo": message,
        "timestamp": datetime.now().isoformat(),
        "received_at": "server"
    }

@app.get("/api/languages")
async def get_supported_languages():
    """지원하는 언어 목록"""
    language_info = {
        "ko": {"name": "한국어", "flag": "🇰🇷", "code": "ko-KR"},
        "en": {"name": "English", "flag": "🇺🇸", "code": "en-US"},
        "ja": {"name": "日本語", "flag": "🇯🇵", "code": "ja-JP"},
        "zh": {"name": "中文", "flag": "🇨🇳", "code": "zh-CN"},
        "fr": {"name": "Français", "flag": "🇫🇷", "code": "fr-FR"}
    }
    
    return {
        "supported_languages": settings.supported_languages,
        "default_language": settings.default_language,
        "language_details": {
            lang: language_info.get(lang, {"name": lang, "flag": "🌐", "code": lang})
            for lang in settings.supported_languages
        }
    }

# 에러 핸들러
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """HTTP 예외 처리"""
    logger.warning(f"HTTP 예외: {exc.status_code} - {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "message": exc.detail,
            "status_code": exc.status_code,
            "timestamp": datetime.now().isoformat()
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """일반 예외 처리"""
    logger.error(f"예상치 못한 오류: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "message": "서버 내부 오류가 발생했습니다.",
            "status_code": 500,
            "timestamp": datetime.now().isoformat()
        }
    )

# 개발용 실행 함수
def run_dev_server():
    """개발 서버 실행"""
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )

if __name__ == "__main__":
    run_dev_server()