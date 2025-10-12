import os
import base64
import requests
import aiohttp
import json
import logging
from typing import Optional, Dict, List
from datetime import datetime, timedelta
import tempfile
from app.services.pronunciation_data_service import pronunciation_data_service

logger = logging.getLogger(__name__)

class ElevenLabsVoiceCloningService:
    """ElevenLabs API를 사용한 음성 복제 서비스 (비동기 수정 버전)"""

    def __init__(self):
        self.api_key = os.getenv("ELEVENLABS_API_KEY")
        self.base_url = "https://api.elevenlabs.io/v1"
        self.data_service = pronunciation_data_service

        if not self.api_key:
            logger.warning("ELEVENLABS_API_KEY가 설정되지 않았습니다.")

    async def create_user_voice_clone(
            self,
            user_id: str,
            voice_sample_base64: str,
            voice_name: Optional[str] = None
    ) -> Dict:
        """사용자 음성 샘플로 voice clone 생성 (DB 우선 확인)"""
        if not self.api_key:
            return {"success": False, "error": "ElevenLabs API 키가 설정되지 않았습니다."}
        if not self.data_service or not self.data_service.supabase:
            return {"success": False, "error": "데이터베이스 서비스에 연결할 수 없습니다."}

        try:
            response = await self.data_service.supabase.table("user_account").select("elevenlabs_voice_id").eq("user_id", user_id).execute()

            if response.data and response.data[0].get("elevenlabs_voice_id"):
                voice_id = response.data[0]["elevenlabs_voice_id"]
                logger.info(f"DB에서 기존 Voice ID 사용: {user_id} -> {voice_id}")
                return {"success": True, "voice_id": voice_id, "cached": True}

            logger.info(f"DB에 Voice ID 없음. {user_id}의 새 목소리를 생성합니다.")

            audio_data = base64.b64decode(voice_sample_base64)
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_file_path = temp_file.name

            new_voice_id = None
            try:
                new_voice_id = await self._create_voice_via_api(
                    user_id,
                    temp_file_path,
                    voice_name or f"PronunciationTutor_{user_id}_{datetime.now().strftime('%Y%m')}"
                )
            finally:
                os.unlink(temp_file_path)

            if not new_voice_id:
                return {"success": False, "error": "ElevenLabs에서 Voice 생성에 실패했습니다."}

            update_response = await self.data_service.supabase.table("user_account").update({
                "elevenlabs_voice_id": new_voice_id
            }).eq("user_id", user_id).execute()

            if not update_response.data:
                logger.warning(f"DB에 Voice ID 업데이트 실패: {user_id} -> {new_voice_id}")

            logger.info(f"새 Voice ID 생성 및 DB 저장 완료: {user_id} -> {new_voice_id}")
            return {"success": True, "voice_id": new_voice_id, "cached": False}

        except Exception as e:
            logger.error(f"Voice clone 생성/조회 오류: {e}")
            return {"success": False, "error": str(e)}

    async def _create_voice_via_api(self, user_id: str, audio_file_path: str, voice_name: str) -> Optional[str]:
        """실제 ElevenLabs API 호출 (비동기 aiohttp 사용)"""
        url = f"{self.base_url}/voices/add"
        headers = {'xi-api-key': self.api_key}

        try:
            async with aiohttp.ClientSession() as session:
                with open(audio_file_path, 'rb') as audio_file:
                    data = aiohttp.FormData()
                    data.add_field('name', voice_name)
                    data.add_field('description', f'Voice clone for user: {user_id}')
                    data.add_field('labels', json.dumps({'user_id': user_id, 'app': 'AI_WAWA'}))
                    data.add_field('files', audio_file, filename=f'{user_id}_sample.wav', content_type='audio/wav')

                    async with session.post(url, headers=headers, data=data, timeout=60) as response:
                        if response.status == 200:
                            response_json = await response.json()
                            voice_id = response_json.get('voice_id')
                            logger.info(f"ElevenLabs API Voice 생성 성공: {user_id} -> {voice_id}")
                            return voice_id
                        else:
                            error_text = await response.text()
                            logger.error(f"ElevenLabs API Voice 생성 실패: {response.status} - {error_text}")
                            return None
        except Exception as e:
            logger.error(f"API 호출 오류: {e}")
            return None

    async def generate_corrected_pronunciation(
            self,
            user_id: str,
            target_text: str,
            pronunciation_analysis: Dict,
            language: str = "en",
            user_level: str = "B1"
    ) -> Dict:
        """사용자 음색으로 교정된 발음 생성"""
        try:
            response = await self.data_service.supabase.table("user_account").select("elevenlabs_voice_id").eq("user_id", user_id).execute()
            if not (response.data and response.data[0].get("elevenlabs_voice_id")):
                return {"success": False, "error": "사용자 목소리가 등록되지 않았습니다. 먼저 목소리를 등록해주세요."}

            voice_id = response.data[0]["elevenlabs_voice_id"]

            corrected_text = self._generate_corrected_text(target_text, pronunciation_analysis)

            audio_result = await self._generate_speech_with_voice(
                voice_id, corrected_text, language, user_level, pronunciation_analysis
            )

            if audio_result["success"]:
                return {"success": True, "corrected_audio_base64": audio_result["audio_base64"], "voice_id": voice_id}
            else:
                return audio_result

        except Exception as e:
            logger.error(f"교정 발음 생성 오류: {e}")
            return {"success": False, "error": str(e)}

    async def _generate_speech_with_voice(
            self,
            voice_id: str,
            text: str,
            language: str,
            user_level: str,
            analysis: Dict = None  # 추가
    ):
        """ElevenLabs로 음성 생성 (발음 분석 기반 설정 조정)"""

        # 기본 Voice Settings
        stability = 0.5
        similarity_boost = 0.75
        style = 0.0
        use_speaker_boost = True

        # 발음 분석 결과에 따라 설정 동적 조정
        if analysis:
            overall_score = analysis.get("overall_score", 100)
            rhythm_score = analysis.get("rhythm_score", 100)
            stress_score = analysis.get("stress_score", 100)
            pitch_score = analysis.get("pitch_score", 100)

            # 전체 점수가 낮으면 명확도 최대화
            if overall_score < 70:
                stability = 0.65
                similarity_boost = 0.85

            # 리듬이 나쁘면 안정성 높임
            if rhythm_score < 50:
                stability = min(stability + 0.15, 0.8)

            # 강세가 나쁘면 명확도 높임
            if stress_score < 65:
                similarity_boost = min(similarity_boost + 0.1, 0.9)

            # 피치가 나쁘면 표현력 추가
            if pitch_score < 80:
                style = 0.2

        # ElevenLabs API 호출
        try:
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

            headers = {
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
                "xi-api-key": self.api_key
            }

            data = {
                "text": text,
                "model_id": "eleven_multilingual_v2",
                "voice_settings": {
                    "stability": stability,
                    "similarity_boost": similarity_boost,
                    "style": style,
                    "use_speaker_boost": use_speaker_boost
                }
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data, headers=headers) as response:
                    if response.status == 200:
                        audio_data = await response.read()
                        audio_base64 = base64.b64encode(audio_data).decode('utf-8')
                        return {
                            "success": True,
                            "audio_base64": audio_base64
                        }
                    else:
                        error = await response.text()
                        return {
                            "success": False,
                            "error": f"ElevenLabs API 오류: {error}"
                        }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def _generate_corrected_text(self, original_text: str, analysis: Dict) -> str:
        """발음 분석 결과에 따라 교정된 텍스트 생성 (ElevenLabs 호환)"""

        corrected_text = original_text

        # 리듬 개선: 자연스러운 쉼표 추가 (ElevenLabs가 실제로 인식함)
        rhythm_score = analysis.get("rhythm_score", 100)
        if rhythm_score < 50:
            words = corrected_text.split()
            enhanced_words = []

            for i, word in enumerate(words):
                enhanced_words.append(word)
                # 3단어마다 쉼표 추가 (문장 시작과 끝 제외)
                if i > 1 and (i + 1) % 3 == 0 and i < len(words) - 2:
                    enhanced_words[-1] += ","

            corrected_text = " ".join(enhanced_words)

        # 강세 개선: 중요 단어를 대문자로 (ElevenLabs가 약간 강조함)
        stress_score = analysis.get("stress_score", 100)
        if stress_score < 65:
            import re
            # 일반적인 중요 단어들 (동사, 명사)
            # 실제로는 품사 태깅이 필요하지만 간단히 처리
            words = corrected_text.split()
            enhanced_words = []

            for word in words:
                clean_word = word.strip(",.!?")
                # 2음절 이상인 단어를 강조 대상으로
                if len(clean_word) >= 4 and clean_word.isalpha():
                    # 원래 구두점 유지하면서 대문자화
                    if word.endswith(','):
                        enhanced_words.append(clean_word.upper() + ',')
                    elif word.endswith('.'):
                        enhanced_words.append(clean_word.upper() + '.')
                    elif word.endswith('?'):
                        enhanced_words.append(clean_word.upper() + '?')
                    else:
                        enhanced_words.append(clean_word.upper())
                else:
                    enhanced_words.append(word)

            corrected_text = " ".join(enhanced_words)

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
            try:
                reset_time = datetime.fromisoformat(limit_info["reset_time"])
                if current_time > reset_time:
                    limit_info["current"] = 0
                    limit_info["reset_time"] = None
            except ValueError:
                # 잘못된 날짜 형식인 경우 리셋
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

    async def generate_corrected_pronunciation_with_storage(
        self,
        user_id: str,
        target_text: str,
        pronunciation_analysis: Dict,
        language: str = "en",
        session_id: str = None
    ) -> Dict:
        """사용자 음색으로 교정된 발음 생성 및 데이터 저장"""

        try:
            # 기존 교정 음성 생성 로직
            result = await self.generate_corrected_pronunciation(
                user_id=user_id,
                target_text=target_text,
                pronunciation_analysis=pronunciation_analysis,
                language=language
            )

            # 성공시 데이터베이스 저장 정보 추가
            if result["success"] and session_id:
                result["session_id"] = session_id
                result["data_storage_ready"] = True

                # 향후 데이터베이스 연동을 위한 메타데이터 추가
                result["metadata"] = {
                    "user_id": user_id,
                    "session_id": session_id,
                    "target_text": target_text,
                    "language": language,
                    "pronunciation_scores": pronunciation_analysis,
                    "generated_at": datetime.now().isoformat()
                }

            return result

        except Exception as e:
            logger.error(f"교정 음성 생성 및 저장 오류: {e}")
            return {"success": False, "error": str(e), "data_storage_ready": False}

# 전역 인스턴스
voice_cloning_service = ElevenLabsVoiceCloningService()
