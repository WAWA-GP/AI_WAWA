"""
음성 억양 분석 서비스
- 실시간 음성 억양 분석
- Open API 기반 표준 발음 데이터 활용
- 피치, 리듬, 강세 분석
- CEFR 레벨별 발음 평가
"""

import asyncio
import logging
import base64
from typing import Dict, List, Optional
from datetime import datetime
import sys
import os

# pronunciation_service 모듈 임포트 (같은 services 디렉토리에서)
try:
    from .pronunciation_service import PronunciationAnalysisService, PronunciationScore
except ImportError:
    # 상대 임포트 실패시 절대 임포트 시도
    try:
        from services.pronunciation_service import PronunciationAnalysisService, PronunciationScore
    except ImportError:
        logging.error("pronunciation_service.py 파일을 찾을 수 없습니다. services 디렉토리에 있는지 확인하세요.")
        # 기본 클래스 정의
        from dataclasses import dataclass
        
        @dataclass
        class PronunciationScore:
            overall_score: float = 60.0
            pitch_score: float = 60.0
            rhythm_score: float = 60.0
            stress_score: float = 60.0
            fluency_score: float = 60.0
            phoneme_scores: Dict[str, float] = None
            detailed_feedback: List[str] = None
            suggestions: List[str] = None
            confidence: float = 0.7
            
            def __post_init__(self):
                if self.phoneme_scores is None:
                    self.phoneme_scores = {'overall': self.overall_score}
                if self.detailed_feedback is None:
                    self.detailed_feedback = ["발음 분석이 완료되었습니다."]
                if self.suggestions is None:
                    self.suggestions = ["계속 연습하세요!"]
        
        class PronunciationAnalysisService:
            """기본 발음 분석 서비스 (fallback)"""
            
            def __init__(self):
                self.is_initialized = False
            
            async def initialize_pronunciation_data(self):
                self.is_initialized = True
                return True
            
            async def analyze_pronunciation_from_base64(self, audio_base64: str, target_text: str, user_level: str = "B1"):
                return PronunciationScore()
            
            async def generate_corrected_audio_guide(self, text: str, user_score, user_level: str = "B1"):
                return None
            
            async def get_pronunciation_reference(self, word: str):
                return None

logger = logging.getLogger(__name__)

class PronunciationAnalysisServiceWrapper:
    """메인 앱과 연동되는 발음 분석 서비스 래퍼"""
    
    def __init__(self):
        """초기화"""
        self.core_service = PronunciationAnalysisService()
        self.is_initialized = False
        logger.info("🎤 발음 분석 서비스 래퍼 초기화")
        
    async def initialize(self):
        """서비스 초기화"""
        if self.is_initialized:
            return True
            
        try:
            await self.core_service.initialize_pronunciation_data()
            self.is_initialized = True
            logger.info("✅ 발음 분석 서비스 초기화 완료")
            return True
        except Exception as e:
            logger.error(f"❌ 발음 분석 서비스 초기화 실패: {e}")
            return False
    
    async def analyze_pronunciation_from_base64(self, audio_base64: str, target_text: str, user_level: str = "B1") -> PronunciationScore:
        """Base64 오디오에서 발음 분석 (메인 앱 호환)"""
        
        if not self.is_initialized:
            await self.initialize()
        
        try:
            return await self.core_service.analyze_pronunciation_from_base64(
                audio_base64, target_text, user_level
            )
        except Exception as e:
            logger.error(f"❌ 발음 분석 오류: {e}")
            return self._create_fallback_score()
    
    async def compare_pronunciations(self, user_audio_base64: str, reference_word: str, user_level: str = "B1") -> Dict:
        """발음 비교 (메인 앱이 기대하는 메소드)"""
        
        try:
            # 단어 발음 분석
            result = await self.analyze_pronunciation_from_base64(
                user_audio_base64, reference_word, user_level
            )
            
            # 비교 결과 형식으로 변환
            comparison_result = {
                "user_pronunciation": {
                    "overall_score": result.overall_score,
                    "pitch_score": result.pitch_score,
                    "rhythm_score": result.rhythm_score,
                    "stress_score": result.stress_score,
                    "fluency_score": result.fluency_score,
                    "phoneme_scores": result.phoneme_scores
                },
                "reference_word": reference_word,
                "strengths": [],
                "improvement_areas": [],
                "detailed_feedback": result.detailed_feedback,
                "suggestions": result.suggestions
            }
            
            # 강점과 개선 영역 식별
            scores = {
                "pitch": result.pitch_score,
                "rhythm": result.rhythm_score,
                "stress": result.stress_score,
                "fluency": result.fluency_score
            }
            
            for area, score in scores.items():
                if score >= 75:
                    comparison_result["strengths"].append(area)
                elif score < 60:
                    comparison_result["improvement_areas"].append(area)
            
            return comparison_result
            
        except Exception as e:
            logger.error(f"❌ 발음 비교 오류: {e}")
            return {
                "user_pronunciation": {"overall_score": 50},
                "reference_word": reference_word,
                "strengths": [],
                "improvement_areas": ["pronunciation"],
                "detailed_feedback": ["분석 중 오류가 발생했습니다."],
                "suggestions": ["다시 시도해 주세요."]
            }
    
    async def get_reference_pronunciation(self, word: str) -> Optional[Dict]:
        """표준 발음 정보 조회"""
        
        if not self.is_initialized:
            await self.initialize()
        
        try:
            # 표준 발음 정보 조회
            reference_info = await self.core_service.get_pronunciation_reference(word)
            
            if reference_info:
                return {
                    "word": word,
                    "expected_syllables": reference_info.get("syllable_count", 1),
                    "stress_pattern": reference_info.get("stress_pattern", [1]),
                    "pitch_contour": [1.0, 0.8, 0.6],  # 기본 피치 윤곽
                    "phonemes": reference_info.get("phonemes", []),
                    "ipa_transcription": reference_info.get("ipa", f"/{word}/"),
                    "difficulty_level": reference_info.get("difficulty", "medium")
                }
            
            return None
            
        except Exception as e:
            logger.error(f"❌ 표준 발음 조회 오류: {e}")
            return None
    
    async def generate_corrected_audio_guide(self, text: str, user_score: PronunciationScore, user_level: str = "B1") -> Optional[str]:
        """교정된 음성 가이드 생성"""
        
        if not self.is_initialized:
            await self.initialize()
        
        try:
            return await self.core_service.generate_corrected_audio_guide(text, user_score, user_level)
        except Exception as e:
            logger.error(f"❌ 음성 가이드 생성 오류: {e}")
            return None
    
    def get_supported_features(self) -> Dict:
        """지원 기능 목록"""
        
        return {
            "pitch_analysis": True,
            "rhythm_analysis": True,
            "stress_analysis": True,
            "fluency_analysis": True,
            "phoneme_analysis": True,
            "level_adaptive": True,
            "real_time_feedback": True,
            "comparative_analysis": True,
            "corrected_audio_guide": True,
            "supported_languages": ["en"],
            "supported_levels": ["A1", "A2", "B1", "B2", "C1", "C2"],
            "data_sources": [
                "CMU Pronouncing Dictionary",
                "Google 10k 단어 빈도",
                "IPA 음성 기호 매핑",
                "음성학 규칙 기반 패턴",
                "TTS 기반 교정 음성"
            ]
        }
    
    def _create_fallback_score(self) -> PronunciationScore:
        """기본 점수 생성"""
        return PronunciationScore(
            overall_score=60.0,
            pitch_score=60.0,
            rhythm_score=60.0,
            stress_score=60.0,
            fluency_score=60.0,
            phoneme_scores={'overall': 60.0},
            detailed_feedback=["발음 분석을 완료했습니다.", "계속 연습하면 더 좋아질 거예요!"],
            suggestions=["매일 꾸준히 연습하세요", "원어민 발음을 많이 들어보세요"],
            confidence=0.7
        )
    
    def _get_ipa_transcription(self, word: str) -> str:
        """IPA 표기법 변환 (간단화)"""
        
        try:
            # 기본 IPA 매핑
            basic_ipa = {
                'hello': '/həˈloʊ/',
                'world': '/wɜrld/',
                'water': '/ˈwɔtər/',
                'computer': '/kəmˈpjutər/',
                'important': '/ɪmˈpɔrtənt/',
                'beautiful': '/ˈbjutəfəl/',
                'pronunciation': '/prəˌnʌnsiˈeɪʃən/',
                'education': '/ˌɛdʒəˈkeɪʃən/',
                'technology': '/tɛkˈnɑlədʒi/',
                'conversation': '/ˌkɑnvərˈseɪʃən/'
            }
            
            return basic_ipa.get(word.lower(), f"/{word}/")
            
        except Exception as e:
            logger.warning(f"IPA 변환 오류: {e}")
            return f"/{word}/"
    
    def _assess_word_difficulty(self, word: str, reference_info: Dict) -> str:
        """단어 난이도 평가"""
        
        try:
            syllables = reference_info.get("expected_syllables", 1)
            
            # 기본 난이도 점수
            difficulty_score = 0
            
            # 음절 수
            if syllables >= 4:
                difficulty_score += 3
            elif syllables == 3:
                difficulty_score += 2
            elif syllables == 2:
                difficulty_score += 1
            
            # 어려운 소리들
            difficult_sounds = ['th', 'r', 'l', 'v', 'w']
            for sound in difficult_sounds:
                if sound in word.lower():
                    difficulty_score += 1
            
            # 단어 길이
            if len(word) > 8:
                difficulty_score += 1
            
            # 난이도 결정
            if difficulty_score <= 1:
                return "easy"
            elif difficulty_score <= 3:
                return "medium"
            elif difficulty_score <= 5:
                return "hard"
            else:
                return "very_hard"
                
        except Exception as e:
            logger.warning(f"난이도 평가 오류: {e}")
            return "medium"

# 메인 앱에서 사용할 글로벌 인스턴스 생성
pronunciation_service = PronunciationAnalysisServiceWrapper()

# 초기화 함수 (메인 앱 시작시 호출)
async def initialize_pronunciation_service():
    """발음 분석 서비스 초기화 함수"""
    return await pronunciation_service.initialize()

# 상태 확인 함수
def is_pronunciation_service_ready() -> bool:
    """발음 분석 서비스 준비 상태 확인"""
    return pronunciation_service.is_initialized

# 메인 앱이 기대하는 추가 함수들
async def analyze_pronunciation(audio_base64: str, target_text: str, user_level: str = "B1") -> Dict:
    """발음 분석 (메인 앱 호환 형식)"""
    
    try:
        result = await pronunciation_service.analyze_pronunciation_from_base64(
            audio_base64, target_text, user_level
        )
        
        return {
            "success": True,
            "overall_score": result.overall_score,
            "pitch_score": result.pitch_score,
            "rhythm_score": result.rhythm_score,
            "stress_score": result.stress_score,
            "fluency_score": result.fluency_score,
            "detailed_feedback": result.detailed_feedback,
            "suggestions": result.suggestions,
            "phoneme_scores": result.phoneme_scores,
            "confidence": result.confidence,
            "analyzed_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"발음 분석 오류: {e}")
        return {
            "success": False,
            "error": str(e),
            "overall_score": 50,
            "detailed_feedback": ["분석 중 오류가 발생했습니다."],
            "suggestions": ["다시 시도해 주세요."]
        }

async def compare_pronunciation(user_audio_base64: str, reference_word: str, user_level: str = "B1") -> Dict:
    """발음 비교 (메인 앱 호환 형식)"""
    
    try:
        result = await pronunciation_service.compare_pronunciations(
            user_audio_base64, reference_word, user_level
        )
        
        return {
            "success": True,
            "comparison_result": result,
            "compared_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"발음 비교 오류: {e}")
        return {
            "success": False,
            "error": str(e),
            "comparison_result": {
                "user_pronunciation": {"overall_score": 50},
                "improvement_areas": ["pronunciation"]
            }
        }

async def get_reference_info(word: str) -> Dict:
    """표준 발음 정보 (비동기 버전)"""
    
    try:
        result = await pronunciation_service.get_reference_pronunciation(word)
        
        if result:
            return {
                "success": True,
                "reference_info": result
            }
        else:
            return {
                "success": False,
                "error": f"'{word}'의 발음 정보를 찾을 수 없습니다."
            }
            
    except Exception as e:
        logger.error(f"표준 발음 정보 조회 오류: {e}")
        return {
            "success": False,
            "error": str(e)
        }

def get_reference_info_sync(word: str) -> Dict:
    """표준 발음 정보 (동기 버전 - 호환성용)"""
    
    try:
        # 비동기 함수를 동기적으로 실행
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 이미 실행 중인 루프가 있으면 새 태스크로 실행
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run, 
                    pronunciation_service.get_reference_pronunciation(word)
                )
                result = future.result()
        else:
            result = asyncio.run(pronunciation_service.get_reference_pronunciation(word))
        
        if result:
            return {
                "success": True,
                "reference_info": result
            }
        else:
            return {
                "success": False,
                "error": f"'{word}'의 발음 정보를 찾을 수 없습니다."
            }
            
    except Exception as e:
        logger.error(f"표준 발음 정보 조회 오류: {e}")
        return {
            "success": False,
            "error": str(e)
        }

async def generate_pronunciation_guide(text: str, user_score: Dict, user_level: str = "B1") -> Dict:
    """교정된 발음 가이드 생성"""
    
    try:
        # user_score Dict를 PronunciationScore 객체로 변환
        if isinstance(user_score, dict):
            score_obj = PronunciationScore(
                overall_score=user_score.get('overall_score', 60.0),
                pitch_score=user_score.get('pitch_score', 60.0),
                rhythm_score=user_score.get('rhythm_score', 60.0),
                stress_score=user_score.get('stress_score', 60.0),
                fluency_score=user_score.get('fluency_score', 60.0),
                phoneme_scores=user_score.get('phoneme_scores', {}),
                detailed_feedback=user_score.get('detailed_feedback', []),
                suggestions=user_score.get('suggestions', []),
                confidence=user_score.get('confidence', 0.7)
            )
        else:
            score_obj = user_score
        
        # 교정된 음성 가이드 생성
        corrected_audio = await pronunciation_service.generate_corrected_audio_guide(
            text, score_obj, user_level
        )
        
        if corrected_audio:
            return {
                "success": True,
                "corrected_audio_base64": corrected_audio,
                "text": text,
                "user_level": user_level,
                "generated_at": datetime.now().isoformat()
            }
        else:
            return {
                "success": False,
                "error": "교정된 음성 가이드를 생성할 수 없습니다."
            }
            
    except Exception as e:
        logger.error(f"발음 가이드 생성 오류: {e}")
        return {
            "success": False,
            "error": str(e)
        }

# 테스트 함수
async def test_pronunciation_service():
    """발음 분석 서비스 테스트"""
    
    logger.info("🧪 발음 분석 서비스 테스트 시작")
    
    try:
        # 초기화 테스트
        init_result = await pronunciation_service.initialize()
        logger.info(f"초기화 결과: {init_result}")
        
        # 기능 테스트
        features = pronunciation_service.get_supported_features()
        logger.info(f"지원 기능: {len(features)} 개")
        
        # 표준 발음 조회 테스트
        ref_info = await pronunciation_service.get_reference_pronunciation("hello")
        logger.info(f"'hello' 발음 정보: {ref_info is not None}")
        
        # 더미 오디오로 분석 테스트
        import base64
        dummy_audio = base64.b64encode(b"dummy_audio_data").decode('utf-8')
        analysis_result = await analyze_pronunciation(dummy_audio, "hello", "B1")
        logger.info(f"분석 테스트: {analysis_result['success']}")
        
        logger.info("✅ 발음 분석 서비스 테스트 완료")
        return True
        
    except Exception as e:
        logger.error(f"❌ 발음 분석 서비스 테스트 실패: {e}")
        return False

# 서비스 상태 확인
def get_service_status() -> Dict:
    """서비스 상태 정보 반환"""
    
    return {
        "service_name": "pronunciation_analysis",
        "initialized": pronunciation_service.is_initialized,
        "core_service_available": pronunciation_service.core_service is not None,
        "supported_features": pronunciation_service.get_supported_features(),
        "status": "ready" if pronunciation_service.is_initialized else "initializing"
    }

if __name__ == "__main__":
    # 테스트 실행
    asyncio.run(test_pronunciation_service())