# services/text_to_speech_service.py

import asyncio
import base64
import io
import os
import tempfile
import wave
import pyttsx3
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)

class TextToSpeechService:
    """텍스트 음성 변환 서비스 클래스"""
    
    def __init__(self):
        self.engine = pyttsx3.init()
        self._configure_engine()
        
    def _configure_engine(self):
        """TTS 엔진 기본 설정"""
        
        # 음성 속도 설정 (기본: 200, 범위: 50-400)
        self.engine.setProperty('rate', 150)
        
        # 음성 볼륨 설정 (범위: 0.0-1.0)
        self.engine.setProperty('volume', 0.9)
        
        # 사용 가능한 음성 확인
        voices = self.engine.getProperty('voices')
        if voices:
            logger.info(f"사용 가능한 음성: {len(voices)}개")
            
    async def text_to_speech_base64(
        self, 
        text: str, 
        language: str = "ko",
        speed: int = 150,
        volume: float = 0.9
    ) -> Optional[str]:
        """텍스트를 음성으로 변환하여 Base64 반환"""
        
        try:
            # 언어별 음성 설정
            self._set_voice_for_language(language)
            
            # 속도와 볼륨 조정
            self.engine.setProperty('rate', speed)
            self.engine.setProperty('volume', volume)
            
            # 비동기 처리
            loop = asyncio.get_event_loop()
            audio_base64 = await loop.run_in_executor(
                None, 
                self._generate_audio_base64, 
                text
            )
            
            return audio_base64
            
        except Exception as e:
            logger.error(f"TTS 변환 오류: {e}")
            return None
    
    def _generate_audio_base64(self, text: str) -> Optional[str]:
        """실제 음성 생성 및 Base64 인코딩 (동기)"""
        
        try:
            # 임시 파일 생성
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_filename = temp_file.name
            
            # 음성 파일 생성
            self.engine.save_to_file(text, temp_filename)
            self.engine.runAndWait()
            
            # 파일을 Base64로 인코딩
            with open(temp_filename, 'rb') as audio_file:
                audio_data = audio_file.read()
                audio_base64 = base64.b64encode(audio_data).decode('utf-8')
            
            # 임시 파일 삭제
            os.unlink(temp_filename)
            
            logger.info(f"TTS 생성 성공: {text[:30]}...")
            return audio_base64
            
        except Exception as e:
            logger.error(f"음성 파일 생성 오류: {e}")
            return None
    
    def _set_voice_for_language(self, language: str):
        """언어에 따른 음성 설정"""
        
        voices = self.engine.getProperty('voices')
        if not voices:
            return
            
        # 언어별 음성 매핑
        language_voice_map = {
            "ko": ["korean", "kr"],
            "en": ["english", "en", "us"],
            "ja": ["japanese", "jp"],
            "zh": ["chinese", "cn"],
            "es": ["spanish", "es"],
            "fr": ["french", "fr"],
            "de": ["german", "de"]
        }
        
        target_keywords = language_voice_map.get(language, ["english", "en"])
        
        # 적합한 음성 찾기
        for voice in voices:
            voice_name = voice.name.lower()
            if any(keyword in voice_name for keyword in target_keywords):
                self.engine.setProperty('voice', voice.id)
                logger.info(f"음성 설정: {voice.name}")
                return
        
        # 기본 음성 사용
        logger.info("기본 음성 사용")
    
    async def get_voice_info(self) -> Dict:
        """현재 음성 설정 정보 반환"""
        
        try:
            voices = self.engine.getProperty('voices')
            current_voice = self.engine.getProperty('voice')
            rate = self.engine.getProperty('rate')
            volume = self.engine.getProperty('volume')
            
            voice_list = []
            for voice in voices:
                voice_list.append({
                    "id": voice.id,
                    "name": voice.name,
                    "language": getattr(voice, 'languages', ['unknown'])
                })
            
            return {
                "current_voice": current_voice,
                "rate": rate,
                "volume": volume,
                "available_voices": voice_list
            }
            
        except Exception as e:
            logger.error(f"음성 정보 조회 오류: {e}")
            return {}
    
    async def test_speech(self, language: str = "ko") -> Optional[str]:
        """테스트 음성 생성"""
        
        test_texts = {
            "ko": "안녕하세요! 음성 합성 테스트입니다.",
            "en": "Hello! This is a text-to-speech test.",
            "ja": "こんにちは！音声合成のテストです。",
            "zh": "你好！这是语音合成测试。",
            "es": "¡Hola! Esta es una prueba de síntesis de voz.",
            "fr": "Bonjour! Ceci est un test de synthèse vocale.",
            "de": "Hallo! Dies ist ein Sprachsynthese-Test."
        }
        
        test_text = test_texts.get(language, test_texts["en"])
        return await self.text_to_speech_base64(test_text, language)
    
    def get_supported_languages(self) -> Dict[str, str]:
        """지원하는 언어 목록 반환"""
        
        return {
            "korean": "ko",
            "english": "en", 
            "japanese": "ja",
            "chinese": "zh",
            "spanish": "es",
            "french": "fr",
            "german": "de"
        }
    
    async def batch_tts(self, texts: list, language: str = "ko") -> list:
        """여러 텍스트를 한번에 음성 변환"""
        
        results = []
        for text in texts:
            audio_base64 = await self.text_to_speech_base64(text, language)
            results.append({
                "text": text,
                "audio_base64": audio_base64,
                "success": audio_base64 is not None
            })
        
        return results

# 전역 인스턴스
tts_service = TextToSpeechService()