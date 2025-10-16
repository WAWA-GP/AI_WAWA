# services/speech_recognition_service.py

import asyncio
import base64
import io
import speech_recognition as sr
from typing import Optional
import wave
import logging
from pydub import AudioSegment

logger = logging.getLogger(__name__)

class SpeechRecognitionService:
    """음성 인식 서비스 클래스"""
    
    def __init__(self):
        self.recognizer = sr.Recognizer()
        # 노이즈 조정
        self.recognizer.energy_threshold = 300
        self.recognizer.dynamic_energy_threshold = True
        
    async def recognize_from_base64(
        self, 
        audio_base64: str, 
        language: str = "ko-KR"
    ) -> Optional[str]:
        """Base64 오디오 데이터에서 텍스트 추출"""
        
        try:
            # Base64 디코딩
            audio_data = base64.b64decode(audio_base64)
            
            # 바이트 데이터를 AudioData로 변환
            audio_file = io.BytesIO(audio_data)
            
            # 비동기 처리를 위해 executor 사용
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, 
                self._recognize_audio_data, 
                audio_data, 
                language
            )
            
            return result
            
        except Exception as e:
            logger.error(f"음성 인식 오류: {e}")
            return None

    def _recognize_audio_data(self, audio_data: bytes, language: str) -> Optional[str]:
        """(수정됨) M4A 오디오 형식을 직접 처리하여 음성을 인식합니다."""
        try:
            # 1. 전달받은 오디오 데이터를 바로 M4A 형식으로 로드합니다.
            logger.info("M4A 형식으로 오디오 데이터 직접 처리 시도...")
            m4a_audio = AudioSegment.from_file(io.BytesIO(audio_data), format="m4a")

            # 2. 음성 인식을 위해 WAV 형식으로 메모리 내에서 변환합니다.
            wav_buffer = io.BytesIO()
            m4a_audio.export(wav_buffer, format="wav")
            wav_buffer.seek(0)

            # 3. 변환된 WAV 데이터로 음성 인식을 진행합니다.
            with sr.AudioFile(wav_buffer) as source:
                # 주변 소음 수준을 오디오 파일 앞부분으로 파악 (0.5초)
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = self.recognizer.record(source)

            text = self.recognizer.recognize_google(
                audio,
                language=language
            )

            logger.info(f"음성 인식 성공 (M4A 처리): {text[:50]}...")
            return text

        except sr.UnknownValueError:
            logger.warning("음성을 인식할 수 없습니다. (Google Speech Recognition)")
            return None # 실패 시 None을 반환하여 AI가 구체적인 오류 메시지를 생성하도록 유도
        except sr.RequestError as e:
            logger.error(f"Google Speech Recognition API 요청 오류: {e}")
            return None
        except Exception as e:
            # pydub이 지원하지 않는 형식이거나 파일이 손상된 경우 등
            logger.error(f"오디오 처리 중 심각한 오류 발생: {e}")
            return None
    
    async def recognize_from_microphone(
        self, 
        language: str = "ko-KR",
        timeout: int = 5
    ) -> Optional[str]:
        """마이크로부터 실시간 음성 인식"""
        
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, 
                self._recognize_from_mic, 
                language, 
                timeout
            )
            
            return result
            
        except Exception as e:
            logger.error(f"마이크 음성 인식 오류: {e}")
            return None
    
    def _recognize_from_mic(self, language: str, timeout: int) -> Optional[str]:
        """마이크 음성 인식 (동기)"""
        
        try:
            with sr.Microphone() as source:
                logger.info("음성을 녹음 중...")
                # 주변 소음 조정
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                # 음성 녹음 (타임아웃 설정)
                audio = self.recognizer.listen(source, timeout=timeout)
            
            # 음성 인식
            text = self.recognizer.recognize_google(audio, language=language)
            logger.info(f"마이크 음성 인식 성공: {text}")
            return text
            
        except sr.WaitTimeoutError:
            logger.warning("음성 입력 타임아웃")
            return None
        except sr.UnknownValueError:
            logger.warning("음성을 인식할 수 없습니다")
            return None
        except sr.RequestError as e:
            logger.error(f"Google Speech Recognition API 오류: {e}")
            return None
    
    def get_supported_languages(self) -> dict:
        """지원하는 언어 목록 반환"""
        
        return {
            "korean": "ko-KR",
            "english": "en-US", 
            "japanese": "ja-JP",
            "chinese": "zh-CN",
            "spanish": "es-ES",
            "french": "fr-FR",
            "german": "de-DE"
        }
    
    async def preprocess_audio(self, audio_data: bytes) -> bytes:
        """오디오 전처리 (노이즈 제거, 음량 정규화)"""
        
        # 향후 오디오 전처리 로직 추가
        # 현재는 원본 데이터 그대로 반환
        return audio_data

# 전역 인스턴스
stt_service = SpeechRecognitionService()
