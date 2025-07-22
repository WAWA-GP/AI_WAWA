"""
애플리케이션 설정 파일
app/config.py
"""

import os
from typing import List
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """애플리케이션 설정"""
    
    # 기본 설정
    app_name: str = "Language Learning AI"
    app_version: str = "1.0.0"
    environment: str = os.getenv("ENVIRONMENT", "development")
    debug: bool = os.getenv("DEBUG", "true").lower() == "true"
    
    # 서버 설정
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))
    
    # 보안 설정
    secret_key: str = os.getenv("SECRET_KEY", "dev-secret-key-change-me")
    
    # OpenAI 설정
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4")
    openai_temperature: float = float(os.getenv("OPENAI_TEMPERATURE", "0.7"))
    openai_max_tokens: int = int(os.getenv("OPENAI_MAX_TOKENS", "1000"))
    
    # 데이터베이스 설정
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./language_learning.db")
    
    # 로깅 설정
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    
    # CORS 설정
    cors_origins: List[str] = [
        "http://localhost:3000",
        "http://localhost:8080",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8080"
    ]
    
    # 지원 언어
    supported_languages: List[str] = ["ko", "en", "ja", "zh", "fr"]
    default_language: str = "ko"
    
    # 파일 업로드 설정
    upload_folder: str = os.getenv("UPLOAD_FOLDER", "./uploads")
    max_file_size: int = int(os.getenv("MAX_FILE_SIZE", "10485760"))  # 10MB
    allowed_audio_extensions: List[str] = ["wav", "mp3", "m4a", "ogg"]
    
    class Config:
        env_file = ".env"
        case_sensitive = False

# 전역 설정 인스턴스
settings = Settings()

# 설정 검증
def validate_settings():
    """중요한 설정들이 제대로 되어 있는지 확인"""
    errors = []
    
    if not settings.openai_api_key or settings.openai_api_key == "":
        errors.append("OPENAI_API_KEY가 설정되지 않았습니다.")
    
    if not settings.openai_api_key.startswith("sk-"):
        errors.append("OPENAI_API_KEY 형식이 올바르지 않습니다. (sk-로 시작해야 함)")
    
    if settings.environment not in ["development", "production", "testing"]:
        errors.append("ENVIRONMENT는 development, production, testing 중 하나여야 합니다.")
    
    if errors:
        print("❌ 설정 오류:")
        for error in errors:
            print(f"  - {error}")
        print("\n📝 .env 파일을 확인해주세요.")
        return False
    
    print("✅ 모든 설정이 올바르게 구성되었습니다!")
    return True

if __name__ == "__main__":
    # 설정 테스트
    print("🔍 설정 확인 중...")
    print(f"앱 이름: {settings.app_name}")
    print(f"환경: {settings.environment}")
    print(f"디버그 모드: {settings.debug}")
    print(f"OpenAI 모델: {settings.openai_model}")
    print(f"지원 언어: {settings.supported_languages}")
    
    validate_settings()