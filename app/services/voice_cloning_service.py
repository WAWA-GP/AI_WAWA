import os
import base64
import requests
import aiohttp
import asyncio
import json
import logging
from typing import Optional, Dict, List
from datetime import datetime, timedelta
import tempfile

logger = logging.getLogger(__name__)

class ElevenLabsVoiceCloningService:
    """ElevenLabs API를 사용한 음성 복제 서비스"""
    
    def __init__(self):
        self.api_key = os.getenv("ELEVENLABS_API_KEY")
        self.base_url = "https://api.elevenlabs.io/v1"
        
        # 사용자별 voice_id 캐시 (실제로는 데이터베이스에 저장해야 함)
        self.user_voices = {}
        
        # API 사용량 제한 관리
        self.rate_limits = {
            "voice_creation": {"max": 10, "period": 3600, "current": 0, "reset_time": None},
            "tts_generation": {"max": 1000, "period": 3600, "current": 0, "reset_time": None}
        }
        
        if not self.api_key:
            logger.warning("ELEVENLABS_API_KEY가 설정되지 않았습니다.")
    
    async def create_user_voice_clone(
        self, 
        user_id: str, 
        voice_sample_base64: str,
        voice_name: Optional[str] = None
    ) -> Dict:
        """사용자 음성 샘플로 voice clone 생성"""
        
        if not self.api_key:
            return {"success": False, "error": "ElevenLabs API 키가 설정되지 않았습니다."}
        
        try:
            # Rate limiting 체크
            if not self._check_rate_limit("voice_creation"):
                return {"success": False, "error": "API 사용량 한도 초과"}
            
            # 기존 voice가 있는지 확인
            if user_id in self.user_voices:
                existing_voice = self.user_voices[user_id]
                logger.info(f"기존 voice 사용: {user_id} -> {existing_voice['voice_id']}")
                return {
                    "success": True, 
                    "voice_id": existing_voice['voice_id'],
                    "created_at": existing_voice['created_at'],
                    "cached": True
                }
            
            # Base64 디코딩 및 임시 파일 저장
            audio_data = base64.b64decode(voice_sample_base64)
            
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_file_path = temp_file.name
            
            # ElevenLabs API 호출
            voice_id = await self._create_voice_via_api(
                user_id, 
                temp_file_path, 
                voice_name or f"PronunciationTutor_{user_id}"
            )
            
            # 임시 파일 삭제
            os.unlink(temp_file_path)
            
            if voice_id:
                # 캐시에 저장
                self.user_voices[user_id] = {
                    "voice_id": voice_id,
                    "created_at": datetime.now().isoformat(),
                    "last_used": datetime.now().isoformat()
                }
                
                return {
                    "success": True,
                    "voice_id": voice_id,
                    "created_at": datetime.now().isoformat(),
                    "cached": False
                }
            else:
                return {"success": False, "error": "Voice 생성에 실패했습니다."}
                
        except Exception as e:
            logger.error(f"Voice clone 생성 오류: {e}")
            return {"success": False, "error": str(e)}
    
    async def _create_voice_via_api(
        self, 
        user_id: str, 
        audio_file_path: str, 
        voice_name: str
    ) -> Optional[str]:
        """실제 ElevenLabs API 호출"""
        
        url = f"{self.base_url}/voices/add"
        
        headers = {
            'xi-api-key': self.api_key
        }
        
        # 파일과 데이터 준비
        with open(audio_file_path, 'rb') as audio_file:
            files = {
                'files': (f'{user_id}_sample.wav', audio_file, 'audio/wav')
            }
            
            data = {
                'name': voice_name,
                'description': f'Voice clone for pronunciation correction - User: {user_id}',
                'labels': json.dumps({
                    'user_id': user_id,
                    'purpose': 'pronunciation_correction',
                    'created': datetime.now().isoformat()
                })
            }
            
            try:
                response = requests.post(url, headers=headers, files=files, data=data)
                
                if response.status_code == 200:
                    result = response.json()
                    voice_id = result.get('voice_id')
                    logger.info(f"Voice 생성 성공: {user_id} -> {voice_id}")
                    return voice_id
                else:
                    logger.error(f"Voice 생성 실패: {response.status_code} - {response.text}")
                    return None
                    
            except Exception as e:
                logger.error(f"API 호출 오류: {e}")
                return None
    
    async def generate_corrected_pronunciation(
        self,
        user_id: str,
        target_text: str,
        pronunciation_analysis: Dict,
        language: str = "en"
    ) -> Dict:
        """사용자 음색으로 교정된 발음 생성"""
        
        try:
            # 사용자 voice_id 확인
            if user_id not in self.user_voices:
                return {
                    "success": False, 
                    "error": "사용자 voice clone이 없습니다. 먼저 음성을 등록해주세요."
                }
            
            voice_id = self.user_voices[user_id]['voice_id']
            
            # 발음 분석 결과에 따른 텍스트 교정
            corrected_text = self._generate_corrected_text(target_text, pronunciation_analysis)
            
            # TTS 생성
            audio_result = await self._generate_speech_with_voice(
                voice_id, 
                corrected_text,
                language
            )
            
            if audio_result["success"]:
                # 사용 시간 업데이트
                self.user_voices[user_id]['last_used'] = datetime.now().isoformat()
                
                return {
                    "success": True,
                    "corrected_audio_base64": audio_result["audio_base64"],
                    "original_text": target_text,
                    "corrected_text": corrected_text,
                    "voice_id": voice_id,
                    "corrections_applied": self._get_corrections_summary(pronunciation_analysis),
                    "generated_at": datetime.now().isoformat()
                }
            else:
                return audio_result
                
        except Exception as e:
            logger.error(f"교정 발음 생성 오류: {e}")
            return {"success": False, "error": str(e)}
    
    async def _generate_speech_with_voice(
        self,
        voice_id: str,
        text: str,
        language: str = "en"
    ) -> Dict:
        """특정 voice로 TTS 생성"""
        
        if not self._check_rate_limit("tts_generation"):
            return {"success": False, "error": "TTS API 사용량 한도 초과"}
        
        url = f"{self.base_url}/text-to-speech/{voice_id}"
        
        headers = {
            'Accept': 'audio/mpeg',
            'Content-Type': 'application/json',
            'xi-api-key': self.api_key
        }
        
        # 언어별 모델 선택
        model_map = {
            "en": "eleven_multilingual_v2",
            "ko": "eleven_multilingual_v2",
            "ja": "eleven_multilingual_v2",
            "zh": "eleven_multilingual_v2"
        }
        
        payload = {
            'text': text,
            'model_id': model_map.get(language, "eleven_multilingual_v2"),
            'voice_settings': {
                'stability': 0.75,
                'similarity_boost': 0.85,
                'style': 0.3,
                'use_speaker_boost': True
            }
        }
        
        try:
            response = requests.post(url, json=payload, headers=headers)
            
            if response.status_code == 200:
                audio_base64 = base64.b64encode(response.content).decode('utf-8')
                logger.info(f"TTS 생성 성공: voice_id={voice_id}")
                return {
                    "success": True,
                    "audio_base64": audio_base64
                }
            else:
                logger.error(f"TTS 생성 실패: {response.status_code} - {response.text}")
                return {
                    "success": False,
                    "error": f"TTS 생성 실패: {response.text}"
                }
                
        except Exception as e:
            logger.error(f"TTS API 호출 오류: {e}")
            return {"success": False, "error": str(e)}
    
    def _generate_corrected_text(self, original_text: str, analysis: Dict) -> str:
        """발음 분석 결과에 따라 교정된 텍스트 생성"""
        
        corrected_text = original_text
        corrections = []
        
        # 점수별 교정 적용
        if analysis.get("pitch_score", 100) < 70:
            # 억양 교정: 문장 끝에 적절한 억양 표시
            if "?" in corrected_text:
                corrected_text = corrected_text.replace("?", "↗?")
            elif "." in corrected_text:
                corrected_text = corrected_text.replace(".", "↘.")
            corrections.append("intonation")
        
        if analysis.get("stress_score", 100) < 70:
            # 강세 교정: 주요 단어에 강세 표시
            corrected_text = self._add_stress_markers(corrected_text)
            corrections.append("stress")
        
        if analysis.get("rhythm_score", 100) < 70:
            # 리듬 교정: 단어 사이에 적절한 간격
            words = corrected_text.split()
            corrected_text = " / ".join(words)  # 명확한 구분
            corrections.append("rhythm")
        
        if analysis.get("fluency_score", 100) < 70:
            # 유창성 교정: 더 천천히 발음하도록 
            corrected_text = f"[천천히] {corrected_text}"
            corrections.append("fluency")
        
        return corrected_text
    
    def _add_stress_markers(self, text: str) -> str:
        """주요 단어에 강세 표시 추가"""
        
        # 강세를 받아야 할 단어들 (내용어)
        stress_words = ['important', 'beautiful', 'computer', 'pronunciation', 'education']
        
        words = text.split()
        marked_words = []
        
        for word in words:
            clean_word = word.lower().strip('.,!?')
            if clean_word in stress_words or len(clean_word) > 6:
                # 강세 표시 (ElevenLabs에서 인식하는 SSML 형태)
                marked_words.append(f"**{word}**")
            else:
                marked_words.append(word)
        
        return " ".join(marked_words)
    
    def _get_corrections_summary(self, analysis: Dict) -> List[str]:
        """적용된 교정 사항 요약"""
        
        corrections = []
        
        if analysis.get("pitch_score", 100) < 70:
            corrections.append("억양 패턴 교정")
        if analysis.get("stress_score", 100) < 70:
            corrections.append("단어 강세 교정")
        if analysis.get("rhythm_score", 100) < 70:
            corrections.append("발음 리듬 교정")
        if analysis.get("fluency_score", 100) < 70:
            corrections.append("발음 속도 조정")
        
        return corrections if corrections else ["기본 발음 교정"]
    
    def _check_rate_limit(self, operation: str) -> bool:
        """API 사용량 제한 확인"""
        
        current_time = datetime.now()
        limit_info = self.rate_limits.get(operation, {})
        
        # 리셋 시간 확인
        if limit_info.get("reset_time"):
            reset_time = datetime.fromisoformat(limit_info["reset_time"])
            if current_time > reset_time:
                limit_info["current"] = 0
                limit_info["reset_time"] = None
        
        # 첫 사용이거나 리셋된 경우
        if not limit_info.get("reset_time"):
            limit_info["reset_time"] = (current_time + timedelta(seconds=limit_info["period"])).isoformat()
        
        # 한도 확인
        if limit_info["current"] < limit_info["max"]:
            limit_info["current"] += 1
            return True
        else:
            return False
    
    async def get_user_voice_info(self, user_id: str) -> Dict:
        """사용자 voice 정보 조회"""
        
        if user_id not in self.user_voices:
            return {"exists": False}
        
        voice_info = self.user_voices[user_id]
        
        return {
            "exists": True,
            "voice_id": voice_info["voice_id"],
            "created_at": voice_info["created_at"],
            "last_used": voice_info["last_used"]
        }
    
    async def delete_user_voice(self, user_id: str) -> Dict:
        """사용자 voice 삭제"""
        
        if user_id not in self.user_voices:
            return {"success": False, "error": "삭제할 voice가 없습니다."}
        
        voice_id = self.user_voices[user_id]["voice_id"]
        
        # ElevenLabs API에서 삭제
        url = f"{self.base_url}/voices/{voice_id}"
        headers = {'xi-api-key': self.api_key}
        
        try:
            response = requests.delete(url, headers=headers)
            
            if response.status_code == 200:
                # 로컬 캐시에서도 삭제
                del self.user_voices[user_id]
                return {"success": True, "message": "Voice가 삭제되었습니다."}
            else:
                return {"success": False, "error": f"삭제 실패: {response.text}"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}

# 전역 인스턴스
voice_cloning_service = ElevenLabsVoiceCloningService()