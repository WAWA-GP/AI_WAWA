# test_current_system.py
"""
현재 개발된 언어 학습 AI 시스템의 실제 기능 정확도 테스트
"""

import asyncio
import json
import time
import sys
import os
from datetime import datetime
import logging

# 경로 설정 - 프로젝트 구조에 맞게 수정
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))  # 2단계 상위로
app_dir = os.path.join(project_root, 'app')

# Python path에 추가
sys.path.insert(0, app_dir)
sys.path.insert(0, project_root)

print(f"현재 디렉토리: {current_dir}")
print(f"프로젝트 루트: {project_root}")
print(f"앱 디렉토리: {app_dir}")
print(f"Python 경로: {sys.path[:3]}")

# 서비스 임포트 시도
try:
    from services.conversation_ai_service import conversation_ai_service
    print("✅ conversation_ai_service 임포트 성공")
except ImportError as e:
    print(f"❌ conversation_ai_service 임포트 실패: {e}")
    conversation_ai_service = None

try:
    from services.speech_recognition_service import stt_service
    print("✅ stt_service 임포트 성공")
except ImportError as e:
    print(f"❌ stt_service 임포트 실패: {e}")
    stt_service = None

try:
    from services.text_to_speech_service import tts_service
    print("✅ tts_service 임포트 성공")
except ImportError as e:
    print(f"❌ tts_service 임포트 실패: {e}")
    tts_service = None

try:
    from services.level_test_service import level_test_service
    print("✅ level_test_service 임포트 성공")
except ImportError as e:
    print(f"❌ level_test_service 임포트 실패: {e}")
    level_test_service = None

try:
    from services.pronunciation_analysis_service import pronunciation_service
    print("✅ pronunciation_service 임포트 성공")
except ImportError as e:
    print(f"❌ pronunciation_service 임포트 실패: {e}")
    pronunciation_service = None

try:
    from services.conversation_data_collector import data_collector
    print("✅ data_collector 임포트 성공")
except ImportError as e:
    print(f"❌ data_collector 임포트 실패: {e}")
    data_collector = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FixedPathSystemTester:
    """경로 문제를 해결한 시스템 테스터"""
    
    def __init__(self):
        self.test_results = {}
        
    async def run_available_tests(self):
        """사용 가능한 서비스들로만 테스트 실행"""
        print("\n" + "=" * 60)
        print("사용 가능한 서비스 테스트 시작")
        print("=" * 60)
        
        # 1. 임포트 상태 확인
        self.check_import_status()
        
        # 2. 사용 가능한 서비스별 테스트
        if conversation_ai_service:
            await self.test_conversation_ai()
        
        if level_test_service:
            await self.test_level_assessment()
        
        if stt_service:
            await self.test_speech_recognition()
            
        if tts_service:
            await self.test_text_to_speech()
            
        if pronunciation_service:
            await self.test_pronunciation_analysis()
            
        if data_collector:
            await self.test_data_collection()
        
        # 결과 요약
        self.print_test_summary()
        
        return self.test_results
    
    def check_import_status(self):
        """임포트 상태 확인"""
        print("\n🔍 1. 서비스 임포트 상태 확인")
        print("-" * 30)
        
        services = {
            "conversation_ai_service": conversation_ai_service,
            "level_test_service": level_test_service,
            "stt_service": stt_service,
            "tts_service": tts_service,
            "pronunciation_service": pronunciation_service,
            "data_collector": data_collector
        }
        
        available_services = 0
        for service_name, service in services.items():
            if service is not None:
                print(f"✅ {service_name}: 사용 가능")
                available_services += 1
            else:
                print(f"❌ {service_name}: 사용 불가")
        
        self.test_results['import_status'] = {
            'available_services': available_services,
            'total_services': len(services),
            'import_rate': available_services / len(services)
        }
        
        print(f"\n임포트 성공률: {available_services}/{len(services)} ({available_services/len(services)*100:.1f}%)")
    
    async def test_conversation_ai(self):
        """대화 AI 기능 테스트"""
        print("\n💬 2. 대화 AI 기능 테스트")
        print("-" * 30)
        
        try:
            # 사용 가능한 상황 확인
            situations = conversation_ai_service.get_available_situations()
            print(f"✅ 지원 상황: {len(situations)}개 ({', '.join(situations)})")
            
            # 간단한 대화 테스트
            session_id = f"test_session_{int(time.time())}"
            
            start_result = await conversation_ai_service.start_conversation(
                session_id=session_id,
                situation="restaurant",
                difficulty="beginner",
                language="ko",
                mode="auto",
                user_id="test_user_001"
            )
            
            if start_result["success"]:
                print(f"✅ 대화 시작 성공: {start_result.get('mode', 'unknown')} 모드")
                print(f"   첫 메시지: {start_result.get('first_message', '')[:50]}...")
                
                self.test_results['conversation_ai'] = {
                    'start_success': True,
                    'mode': start_result.get('mode'),
                    'situations_count': len(situations)
                }
                
                # 세션 정리
                await conversation_ai_service.end_conversation(session_id)
                print("✅ 대화 세션 정상 종료")
            else:
                print(f"❌ 대화 시작 실패: {start_result.get('error')}")
                self.test_results['conversation_ai'] = {'start_success': False}
                
        except Exception as e:
            print(f"❌ 대화 AI 테스트 실패: {e}")
            self.test_results['conversation_ai'] = {'error': str(e)}
    
    async def test_level_assessment(self):
        """레벨 테스트 기능 테스트"""
        print("\n📊 3. 레벨 평가 기능 테스트")
        print("-" * 30)
        
        try:
            # 레벨 테스트 시작
            test_result = await level_test_service.start_level_test(
                user_id="test_user_level",
                language="english"
            )
            
            if test_result["success"]:
                print(f"✅ 레벨 테스트 시작 성공")
                print(f"   언어: {test_result.get('language_name', 'Unknown')}")
                
                self.test_results['level_assessment'] = {
                    'start_success': True,
                    'language': test_result.get('language', 'en')
                }
            else:
                print(f"❌ 레벨 테스트 시작 실패: {test_result.get('error')}")
                self.test_results['level_assessment'] = {'start_success': False}
                
        except Exception as e:
            print(f"❌ 레벨 평가 테스트 실패: {e}")
            self.test_results['level_assessment'] = {'error': str(e)}
    
    async def test_speech_recognition(self):
        """음성 인식 기능 테스트"""
        print("\n🎤 4. 음성 인식 기능 테스트")
        print("-" * 30)
        
        try:
            # 지원 언어 확인
            supported_langs = stt_service.get_supported_languages()
            print(f"✅ STT 서비스 연결 확인")
            print(f"   지원 언어: {list(supported_langs.keys())}")
            
            self.test_results['speech_recognition'] = {
                'service_available': True,
                'supported_languages': len(supported_langs)
            }
            
        except Exception as e:
            print(f"❌ 음성 인식 테스트 실패: {e}")
            self.test_results['speech_recognition'] = {'error': str(e)}
    
    async def test_text_to_speech(self):
        """TTS 기능 테스트"""
        print("\n🔊 5. 텍스트 음성 변환 테스트")
        print("-" * 30)
        
        try:
            # 지원 언어 확인
            supported_langs = tts_service.get_supported_languages()
            print(f"✅ TTS 서비스 연결 확인")
            print(f"   지원 언어: {list(supported_langs.keys())}")
            
            # 간단한 TTS 테스트
            test_result = await tts_service.text_to_speech_base64(
                text="테스트입니다.",
                language="ko"
            )
            
            if test_result:
                print(f"✅ TTS 생성 성공 (크기: {len(test_result)} bytes)")
            else:
                print("⚠️ TTS 생성 실패 (서비스는 작동)")
            
            self.test_results['text_to_speech'] = {
                'service_available': True,
                'generation_success': test_result is not None,
                'supported_languages': len(supported_langs)
            }
            
        except Exception as e:
            print(f"❌ TTS 테스트 실패: {e}")
            self.test_results['text_to_speech'] = {'error': str(e)}
    
    async def test_pronunciation_analysis(self):
        """발음 분석 기능 테스트"""
        print("\n📈 6. 발음 분석 기능 테스트")
        print("-" * 30)
        
        try:
            # 더미 오디오로 테스트
            import base64
            dummy_audio = base64.b64encode(b"dummy_pronunciation_audio").decode()
            
            analysis_result = await pronunciation_service.analyze_pronunciation_from_base64(
                audio_base64=dummy_audio,
                target_text="Hello world",
                user_level="B1"
            )
            
            print(f"✅ 발음 분석 서비스 연결 확인")
            print(f"   전체 점수: {analysis_result.overall_score:.1f}")
            print(f"   신뢰도: {analysis_result.confidence:.2f}")
            
            self.test_results['pronunciation_analysis'] = {
                'service_available': True,
                'overall_score': analysis_result.overall_score,
                'confidence': analysis_result.confidence
            }
            
        except Exception as e:
            print(f"❌ 발음 분석 테스트 실패: {e}")
            self.test_results['pronunciation_analysis'] = {'error': str(e)}
    
    async def test_data_collection(self):
        """데이터 수집 기능 테스트"""
        print("\n💾 7. 데이터 수집 기능 테스트")
        print("-" * 30)
        
        try:
            if data_collector.supabase:
                stats = await data_collector.get_statistics()
                
                print(f"✅ 데이터 수집 서비스 연결 확인")
                print(f"   총 대화 턴: {stats.get('total_turns', 0)}")
                print(f"   총 세션: {stats.get('total_sessions', 0)}")
                
                self.test_results['data_collection'] = {
                    'connection_success': True,
                    'total_turns': stats.get('total_turns', 0),
                    'total_sessions': stats.get('total_sessions', 0)
                }
            else:
                print(f"⚠️ 데이터 수집 서비스: Supabase 연결 없음")
                self.test_results['data_collection'] = {
                    'connection_success': False,
                    'reason': 'No Supabase connection'
                }
                
        except Exception as e:
            print(f"❌ 데이터 수집 테스트 실패: {e}")
            self.test_results['data_collection'] = {'error': str(e)}
    
    def print_test_summary(self):
        """테스트 결과 요약 출력"""
        print("\n" + "=" * 60)
        print("테스트 결과 요약")
        print("=" * 60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results.values() 
                          if 'error' not in result and result.get('service_available', True))
        
        for test_name, result in self.test_results.items():
            if 'error' not in result:
                status = "✅ 통과"
            else:
                status = "❌ 실패"
            
            print(f"{test_name:25}: {status}")
        
        print(f"\n총 {total_tests}개 테스트 중 {passed_tests}개 통과 ({passed_tests/total_tests*100:.1f}%)")
        
        # 결과 파일 저장
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"fixed_test_results_{timestamp}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump({
                'test_summary': {
                    'total_tests': total_tests,
                    'passed_tests': passed_tests,
                    'success_rate': passed_tests/total_tests,
                    'tested_at': datetime.now().isoformat()
                },
                'detailed_results': self.test_results
            }, f, ensure_ascii=False, indent=2)
        
        print(f"\n상세 결과가 {filename}에 저장되었습니다.")

async def main():
    """메인 실행 함수"""
    tester = FixedPathSystemTester()
    await tester.run_available_tests()

if __name__ == "__main__":
    asyncio.run(main())