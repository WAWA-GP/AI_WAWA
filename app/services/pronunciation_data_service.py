# services/pronunciation_data_service.py

import json
import base64
import wave
import io
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from supabase import create_client, Client
import os

logger = logging.getLogger(__name__)

class PronunciationDataService:
    """발음 분석 데이터를 Supabase에 저장하는 서비스"""

    def __init__(self):
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_KEY")

        if not self.supabase_url or not self.supabase_key:
            logger.error("Supabase 설정이 없습니다.")
            self.supabase = None
        else:
            try:
                self.supabase: Client = create_client(self.supabase_url, self.supabase_key)
                logger.info("🎤 발음 데이터 서비스 초기화 완료")
            except Exception as e:
                logger.error(f"Supabase 초기화 오류: {e}")
                self.supabase = None

    async def create_pronunciation_session(
            self,
            user_id: str,
            session_id: str,
            target_text: str,
            language: str = "en",
            user_level: str = "B1"
    ) -> Optional[str]:
        """새로운 발음 세션 생성"""

        if not self.supabase:
            logger.warning("Supabase가 초기화되지 않음")
            return None

        try:
            session_data = {
                'user_id': user_id,
                'session_id': session_id,
                'target_text': target_text,
                'language': language,
                'user_level': user_level,
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            }

            response = self.supabase.table('pronunciation_sessions').insert(session_data).execute()

            if response.data:
                pronunciation_session_id = response.data[0]['id']
                logger.info(f"🎯 발음 세션 생성: {session_id} -> {pronunciation_session_id}")
                return pronunciation_session_id
            else:
                logger.error("발음 세션 생성 실패")
                return None

        except Exception as e:
            logger.error(f"발음 세션 생성 오류: {e}")
            return None

    async def save_user_audio(
            self,
            pronunciation_session_id: str,
            user_audio_base64: str,
            file_format: str = "wav"
    ) -> bool:
        """사용자 원본 음성 저장"""

        if not self.supabase:
            return False

        try:
            # 오디오 메타데이터 추출
            duration, file_size = self._extract_audio_metadata(user_audio_base64)

            audio_data = {
                'pronunciation_session_id': pronunciation_session_id,
                'audio_type': 'user_original',
                'audio_data_base64': user_audio_base64,
                'file_format': file_format,
                'duration_seconds': duration,
                'file_size_bytes': file_size,
                'created_at': datetime.now().isoformat()
            }

            response = self.supabase.table('pronunciation_audio_files').insert(audio_data).execute()

            if response.data:
                logger.info(f"🎵 사용자 음성 저장 완료: {pronunciation_session_id}")
                return True
            else:
                logger.error("사용자 음성 저장 실패")
                return False

        except Exception as e:
            logger.error(f"사용자 음성 저장 오류: {e}")
            return False

    async def save_corrected_audio(
            self,
            pronunciation_session_id: str,
            corrected_audio_base64: str,
            file_format: str = "wav"
    ) -> bool:
        """교정된 음성 저장"""

        if not self.supabase:
            return False

        try:
            # 오디오 메타데이터 추출
            duration, file_size = self._extract_audio_metadata(corrected_audio_base64)

            audio_data = {
                'pronunciation_session_id': pronunciation_session_id,
                'audio_type': 'corrected_pronunciation',
                'audio_data_base64': corrected_audio_base64,
                'file_format': file_format,
                'duration_seconds': duration,
                'file_size_bytes': file_size,
                'created_at': datetime.now().isoformat()
            }

            response = self.supabase.table('pronunciation_audio_files').insert(audio_data).execute()

            if response.data:
                logger.info(f"🔧 교정 음성 저장 완료: {pronunciation_session_id}")
                return True
            else:
                logger.error("교정 음성 저장 실패")
                return False

        except Exception as e:
            logger.error(f"교정 음성 저장 오류: {e}")
            return False

    async def save_analysis_result(
            self,
            pronunciation_session_id: str,
            analysis_result: Dict[str, Any]
    ) -> bool:
        """발음 분석 결과 저장"""

        if not self.supabase:
            return False

        try:
            analysis_data = {
                'pronunciation_session_id': pronunciation_session_id,
                'overall_score': analysis_result.get('overall_score', 0.0),
                'pitch_score': analysis_result.get('pitch_score', 0.0),
                'rhythm_score': analysis_result.get('rhythm_score', 0.0),
                'stress_score': analysis_result.get('stress_score', 0.0),
                'fluency_score': analysis_result.get('fluency_score', 0.0),
                'phoneme_scores': json.dumps(analysis_result.get('phoneme_scores', {})),
                'detailed_feedback': json.dumps(analysis_result.get('detailed_feedback', [])),
                'suggestions': json.dumps(analysis_result.get('suggestions', [])),
                'confidence': analysis_result.get('confidence', 0.0),
                'created_at': datetime.now().isoformat()
            }

            response = self.supabase.table('pronunciation_analysis_results').insert(analysis_data).execute()

            if response.data:
                logger.info(f"📊 분석 결과 저장 완료: {pronunciation_session_id}")
                return True
            else:
                logger.error("분석 결과 저장 실패")
                return False

        except Exception as e:
            logger.error(f"분석 결과 저장 오류: {e}")
            return False

    async def get_user_pronunciation_history(
            self,
            user_id: str,
            limit: int = 50
    ) -> List[Dict]:
        """사용자 발음 연습 기록 조회"""

        if not self.supabase:
            return []

        try:
            response = self.supabase.table('pronunciation_sessions').select(
                '''
                id,
                session_id,
                target_text,
                language,
                user_level,
                created_at,
                pronunciation_analysis_results (
                    overall_score,
                    pitch_score,
                    rhythm_score,
                    stress_score,
                    fluency_score,
                    confidence
                ),
                pronunciation_audio_files (
                    audio_type,
                    duration_seconds,
                    file_size_bytes
                )
                '''
            ).eq('user_id', user_id).order('created_at', desc=True).limit(limit).execute()

            return response.data if response.data else []

        except Exception as e:
            logger.error(f"사용자 기록 조회 오류: {e}")
            return []

    async def get_pronunciation_session_details(
            self,
            session_id: str
    ) -> Optional[Dict]:
        """특정 세션의 상세 정보 조회"""

        if not self.supabase:
            return None

        try:
            response = self.supabase.table('pronunciation_sessions').select(
                '''
                *,
                pronunciation_analysis_results (*),
                pronunciation_audio_files (*)
                '''
            ).eq('session_id', session_id).execute()

            if response.data:
                return response.data[0]
            else:
                return None

        except Exception as e:
            logger.error(f"세션 상세 조회 오류: {e}")
            return None

    async def get_audio_files(
            self,
            pronunciation_session_id: str
    ) -> Dict[str, str]:
        """세션의 음성 파일들 조회"""

        if not self.supabase:
            return {}

        try:
            response = self.supabase.table('pronunciation_audio_files').select(
                'audio_type, audio_data_base64'
            ).eq('pronunciation_session_id', pronunciation_session_id).execute()

            audio_files = {}
            if response.data:
                for file_data in response.data:
                    audio_files[file_data['audio_type']] = file_data['audio_data_base64']

            return audio_files

        except Exception as e:
            logger.error(f"음성 파일 조회 오류: {e}")
            return {}

    async def get_user_statistics(
            self,
            user_id: str
    ) -> Dict[str, Any]:
        """사용자 발음 연습 통계"""

        if not self.supabase:
            return {}

        try:
            # 전체 세션 수
            sessions_response = self.supabase.table('pronunciation_sessions').select(
                'id', count='exact'
            ).eq('user_id', user_id).execute()

            total_sessions = sessions_response.count

            # 평균 점수 조회
            scores_response = self.supabase.table('pronunciation_sessions').select(
                '''
                pronunciation_analysis_results (
                    overall_score,
                    pitch_score,
                    rhythm_score,
                    stress_score,
                    fluency_score
                )
                '''
            ).eq('user_id', user_id).execute()

            scores = []
            if scores_response.data:
                for session in scores_response.data:
                    if session.get('pronunciation_analysis_results'):
                        for result in session['pronunciation_analysis_results']:
                            scores.append(result)

            # 평균 계산
            if scores:
                avg_scores = {
                    'overall_score': sum(s['overall_score'] for s in scores) / len(scores),
                    'pitch_score': sum(s['pitch_score'] for s in scores) / len(scores),
                    'rhythm_score': sum(s['rhythm_score'] for s in scores) / len(scores),
                    'stress_score': sum(s['stress_score'] for s in scores) / len(scores),
                    'fluency_score': sum(s['fluency_score'] for s in scores) / len(scores)
                }
            else:
                avg_scores = {
                    'overall_score': 0,
                    'pitch_score': 0,
                    'rhythm_score': 0,
                    'stress_score': 0,
                    'fluency_score': 0
                }

            # 언어별 연습 분포
            language_response = self.supabase.table('pronunciation_sessions').select(
                'language'
            ).eq('user_id', user_id).execute()

            language_counts = {}
            if language_response.data:
                for session in language_response.data:
                    lang = session['language']
                    language_counts[lang] = language_counts.get(lang, 0) + 1

            return {
                'total_sessions': total_sessions,
                'average_scores': avg_scores,
                'language_distribution': language_counts,
                'total_analyzed_sessions': len(scores)
            }

        except Exception as e:
            logger.error(f"통계 조회 오류: {e}")
            return {}

    def _extract_audio_metadata(self, audio_base64: str) -> tuple:
        """Base64 오디오에서 메타데이터 추출"""

        try:
            audio_data = base64.b64decode(audio_base64)
            file_size = len(audio_data)

            # WAV 파일의 경우 헤더에서 지속시간 추출
            try:
                audio_io = io.BytesIO(audio_data)
                with wave.open(audio_io, 'rb') as wav_file:
                    frames = wav_file.getnframes()
                    framerate = wav_file.getframerate()
                    duration = frames / framerate
                    return duration, file_size
            except:
                # WAV가 아니거나 읽기 실패시 추정값
                return 2.0, file_size  # 기본 2초로 추정

        except Exception as e:
            logger.warning(f"오디오 메타데이터 추출 오류: {e}")
            return 2.0, 0

# 전역 인스턴스
pronunciation_data_service = PronunciationDataService()
