"""
각 기능별 개별 테스트 - 더 자세한 정확도 확인
"""

import asyncio
import base64
import time
import sys
import os

# 경로 설정 - test_current_system.py와 동일하게
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
    from services.level_test_service import level_test_service
    print("✅ level_test_service 임포트 성공")
except ImportError as e:
    print(f"❌ level_test_service 임포트 실패: {e}")
    level_test_service = None

# 1. 대화 AI 응답 품질 테스트
async def test_conversation_quality():
    """다양한 입력에 대한 AI 응답 품질 테스트"""
    print("\n🤖 대화 AI 응답 품질 테스트")
    print("-" * 40)
    
    if conversation_ai_service is None:
        print("❌ conversation_ai_service를 사용할 수 없습니다.")
        return 0.0
    
    test_cases = [
        {
            "situation": "restaurant",
            "user_input": "I want to order food",
            "expected_keywords": ["menu", "order", "what", "like"]
        },
        {
            "situation": "airport", 
            "user_input": "Where is gate 5?",
            "expected_keywords": ["gate", "direction", "follow", "signs"]
        },
        {
            "situation": "hotel",
            "user_input": "I have a reservation",
            "expected_keywords": ["name", "check", "reservation", "room"]
        }
    ]
    
    total_score = 0
    
    for i, test_case in enumerate(test_cases, 1):
        session_id = f"quality_test_{i}"
        
        try:
            # 대화 시작
            start_result = await conversation_ai_service.start_conversation(
                session_id=session_id,
                situation=test_case["situation"],
                user_id="test_user"
            )
            
            if start_result["success"]:
                # 사용자 입력 처리
                response = await conversation_ai_service.process_user_response(
                    session_id=session_id,
                    user_message=test_case["user_input"]
                )
                
                if response["success"]:
                    ai_message = response.get("ai_message", "").lower()
                    
                    # 키워드 매칭 점수 계산
                    matched = sum(1 for keyword in test_case["expected_keywords"] 
                                if keyword.lower() in ai_message)
                    score = matched / len(test_case["expected_keywords"])
                    total_score += score
                    
                    print(f"테스트 {i}: {test_case['situation']}")
                    print(f"  입력: {test_case['user_input']}")
                    print(f"  AI 응답: {response.get('ai_message', '')[:80]}...")
                    print(f"  관련성 점수: {score:.2f} ({matched}/{len(test_case['expected_keywords'])})")
                    print()
                else:
                    print(f"테스트 {i}: 응답 처리 실패")
            else:
                print(f"테스트 {i}: 대화 시작 실패")
        
        except Exception as e:
            print(f"테스트 {i}: 오류 발생 - {e}")
        
        finally:
            # 세션 정리
            try:
                await conversation_ai_service.end_conversation(session_id)
            except:
                pass
    
    avg_score = total_score / len(test_cases) if test_cases else 0
    print(f"평균 응답 품질 점수: {avg_score:.2f}")
    print(f"품질 등급: {'우수' if avg_score >= 0.8 else '양호' if avg_score >= 0.6 else '개선필요'}")
    
    return avg_score

# 2. 레벨 테스트 일관성 확인
async def test_level_consistency():
    """동일한 답변 패턴으로 레벨 테스트 일관성 확인"""
    print("\n📊 레벨 테스트 일관성 확인")
    print("-" * 40)
    
    if level_test_service is None:
        print("❌ level_test_service를 사용할 수 없습니다.")
        return 0.0
    
    # 동일한 답변 패턴으로 3번 테스트
    answer_pattern = ["A", "B", "A", "A", "B", "A", "B", "A"]  # 가상의 일관된 답변
    results = []
    
    for test_num in range(3):
        print(f"테스트 {test_num + 1} 실행 중...")
        
        try:
            # 레벨 테스트 시작
            test_result = await level_test_service.start_level_test(
                user_id=f"consistency_test_{test_num}",
                language="english"
            )
            
            if test_result["success"]:
                session_id = test_result["session_id"]
                
                # 미리 정한 답변 패턴으로 답변
                for answer in answer_pattern:
                    # 현재 질문 정보 가져오기 (간단화)
                    answer_result = await level_test_service.submit_answer(
                        session_id=session_id,
                        question_id=f"q_{test_num}_{len(results)}",
                        answer=answer
                    )
                    
                    if not answer_result["success"]:
                        break
                        
                    if answer_result.get("status") == "completed":
                        final_result = answer_result.get("final_result", {})
                        final_level = final_result.get("final_level", "Unknown")
                        results.append(final_level)
                        print(f"  결과: {final_level}")
                        break
            else:
                print(f"  레벨 테스트 시작 실패: {test_result.get('message', 'Unknown error')}")
                
        except Exception as e:
            print(f"  테스트 {test_num + 1} 오류: {e}")
    
    # 일관성 분석
    if results:
        unique_levels = set(results)
        consistency_score = (len(results) - len(unique_levels) + 1) / len(results)
        
        print(f"\n일관성 결과:")
        print(f"  테스트 결과: {results}")
        print(f"  일관성 점수: {consistency_score:.2f}")
        print(f"  일관성 등급: {'높음' if consistency_score >= 0.8 else '보통' if consistency_score >= 0.6 else '낮음'}")
        
        return consistency_score
    else:
        print("테스트 실행 실패")
        return 0.0

# 3. 응답 시간 성능 테스트
async def test_response_time():
    """시스템 응답 시간 측정"""
    print("\n⏱️ 응답 시간 성능 테스트")
    print("-" * 40)
    
    if conversation_ai_service is None:
        print("❌ conversation_ai_service를 사용할 수 없습니다.")
        return 0.0
    
    response_times = []
    
    for i in range(5):
        start_time = time.time()
        
        try:
            # 대화 시작부터 응답까지 시간 측정
            session_id = f"speed_test_{i}"
            
            start_result = await conversation_ai_service.start_conversation(
                session_id=session_id,
                situation="restaurant",
                user_id="speed_test_user"
            )
            
            if start_result["success"]:
                response_result = await conversation_ai_service.process_user_response(
                    session_id=session_id,
                    user_message="Hello, I need help"
                )
                
                end_time = time.time()
                response_time = end_time - start_time
                response_times.append(response_time)
                
                print(f"테스트 {i+1}: {response_time:.2f}초")
                
                # 정리
                await conversation_ai_service.end_conversation(session_id)
            else:
                print(f"테스트 {i+1}: 대화 시작 실패")
                
        except Exception as e:
            print(f"테스트 {i+1}: 오류 발생 - {e}")
    
    if response_times:
        avg_time = sum(response_times) / len(response_times)
        max_time = max(response_times)
        min_time = min(response_times)
        
        print(f"\n응답 시간 분석:")
        print(f"  평균: {avg_time:.2f}초")
        print(f"  최대: {max_time:.2f}초") 
        print(f"  최소: {min_time:.2f}초")
        print(f"  성능 등급: {'우수' if avg_time < 1.0 else '양호' if avg_time < 2.0 else '개선필요'}")
        
        return avg_time
    else:
        print("응답 시간 측정 실패")
        return 0.0

# 4. 다국어 지원 테스트
async def test_multilingual_support():
    """다국어 지원 기능 테스트"""
    print("\n🌍 다국어 지원 기능 테스트")
    print("-" * 40)
    
    if level_test_service is None:
        print("❌ level_test_service를 사용할 수 없습니다.")
        return {}
    
    languages = ["ko", "en", "ja", "zh", "fr"]
    test_results = {}
    
    for lang in languages:
        print(f"언어 테스트: {lang}")
        
        try:
            # 레벨 테스트 다국어 지원 확인
            language_map = {
                "en": "english",
                "ko": "korean", 
                "ja": "japanese",
                "zh": "chinese",
                "fr": "french"
            }
            
            test_result = await level_test_service.start_level_test(
                user_id=f"multilang_test_{lang}",
                language=language_map.get(lang, "english")
            )
            
            if test_result["success"]:
                question = test_result.get("current_question", {})
                question_lang = question.get("language", "unknown")
                print(f"  레벨 테스트: ✅ (언어: {question_lang})")
                test_results[lang] = {"level_test": True, "detected_language": question_lang}
            else:
                print(f"  레벨 테스트: ❌ - {test_result.get('message', 'Unknown error')}")
                test_results[lang] = {"level_test": False}
                
        except Exception as e:
            print(f"  오류: {e}")
            test_results[lang] = {"error": str(e)}
    
    # 결과 요약
    successful_langs = sum(1 for result in test_results.values() 
                          if result.get("level_test", False))
    
    print(f"\n다국어 지원 결과:")
    print(f"  지원 언어: {successful_langs}/{len(languages)}")
    print(f"  지원률: {successful_langs/len(languages)*100:.1f}%")
    
    return test_results

# 5. 오류 처리 테스트
async def test_error_handling():
    """시스템 오류 처리 능력 테스트"""
    print("\n🛡️ 오류 처리 능력 테스트")
    print("-" * 40)
    
    if conversation_ai_service is None and level_test_service is None:
        print("❌ 테스트할 서비스가 없습니다.")
        return 0.0
    
    error_tests = []
    
    if conversation_ai_service:
        error_tests.extend([
            {
                "name": "빈 메시지 처리",
                "test": lambda: conversation_ai_service.process_user_response("test_session", "")
            },
            {
                "name": "존재하지 않는 세션",
                "test": lambda: conversation_ai_service.process_user_response("nonexistent_session", "hello")
            }
        ])
    
    if level_test_service:
        error_tests.append({
            "name": "잘못된 답변 형식",
            "test": lambda: level_test_service.submit_answer("invalid_session", "invalid_q", "INVALID_ANSWER")
        })
    
    if not error_tests:
        print("테스트할 서비스가 없습니다.")
        return 0.0
    
    error_handling_score = 0
    
    for test_case in error_tests:
        try:
            result = await test_case["test"]()
            
            # 오류를 적절히 처리했는지 확인
            if isinstance(result, dict) and not result.get("success", True):
                print(f"  {test_case['name']}: ✅ (적절한 오류 처리)")
                error_handling_score += 1
            else:
                print(f"  {test_case['name']}: ⚠️ (오류 처리 개선 필요)")
                
        except Exception as e:
            print(f"  {test_case['name']}: ❌ (예외 발생: {str(e)[:50]})")
    
    handling_rate = error_handling_score / len(error_tests)
    print(f"\n오류 처리 점수: {handling_rate:.2f}")
    print(f"안정성 등급: {'높음' if handling_rate >= 0.8 else '보통' if handling_rate >= 0.6 else '낮음'}")
    
    return handling_rate

# 6. 메모리 사용량 테스트
async def test_memory_usage():
    """메모리 사용량 및 세션 관리 테스트"""
    print("\n💾 메모리 사용량 테스트")
    print("-" * 40)
    
    if conversation_ai_service is None:
        print("❌ conversation_ai_service를 사용할 수 없습니다.")
        return {
            "initial_memory": 0,
            "peak_memory": 0,
            "final_memory": 0,
            "memory_efficiency": 0.5
        }
    
    try:
        import psutil
        
        # 시작 메모리 사용량
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        print(f"초기 메모리 사용량: {initial_memory:.1f} MB")
        
        # 다중 세션 생성
        sessions = []
        for i in range(10):
            session_id = f"memory_test_{i}"
            
            try:
                result = await conversation_ai_service.start_conversation(
                    session_id=session_id,
                    situation="restaurant",
                    user_id=f"memory_user_{i}"
                )
                
                if result["success"]:
                    sessions.append(session_id)
            except Exception as e:
                print(f"세션 {i} 생성 실패: {e}")
        
        # 중간 메모리 사용량
        mid_memory = process.memory_info().rss / 1024 / 1024
        print(f"세션 생성 후: {mid_memory:.1f} MB (+{mid_memory-initial_memory:.1f} MB)")
        
        # 각 세션에서 대화 진행
        for session_id in sessions:
            try:
                await conversation_ai_service.process_user_response(
                    session_id=session_id,
                    user_message="Hello, I want to test memory usage"
                )
            except Exception as e:
                print(f"세션 {session_id} 대화 실패: {e}")
        
        # 대화 후 메모리 사용량
        after_conversation_memory = process.memory_info().rss / 1024 / 1024
        print(f"대화 진행 후: {after_conversation_memory:.1f} MB (+{after_conversation_memory-initial_memory:.1f} MB)")
        
        # 세션 정리
        for session_id in sessions:
            try:
                await conversation_ai_service.end_conversation(session_id)
            except Exception as e:
                print(f"세션 {session_id} 정리 실패: {e}")
        
        # 정리 후 메모리 사용량
        final_memory = process.memory_info().rss / 1024 / 1024
        print(f"세션 정리 후: {final_memory:.1f} MB (+{final_memory-initial_memory:.1f} MB)")
        
        memory_efficiency = 1.0 - min((final_memory - initial_memory) / 100, 1.0)  # 100MB 증가를 기준으로
        print(f"메모리 효율성: {memory_efficiency:.2f}")
        
        return {
            "initial_memory": initial_memory,
            "peak_memory": after_conversation_memory,
            "final_memory": final_memory,
            "memory_efficiency": memory_efficiency
        }
        
    except ImportError:
        print("psutil 라이브러리가 설치되지 않아 메모리 테스트를 건너뜁니다.")
        print("설치 명령: pip install psutil")
        return {
            "initial_memory": 0,
            "peak_memory": 0,
            "final_memory": 0,
            "memory_efficiency": 0.5
        }
    except Exception as e:
        print(f"메모리 테스트 오류: {e}")
        return {
            "initial_memory": 0,
            "peak_memory": 0,
            "final_memory": 0,
            "memory_efficiency": 0.5
        }

# 통합 실행 함수
async def run_detailed_tests():
    """모든 상세 테스트 실행"""
    print("=" * 60)
    print("상세 기능 정확도 테스트 시작")
    print("=" * 60)
    
    results = {}
    
    # 각 테스트 실행
    try:
        results["conversation_quality"] = await test_conversation_quality()
    except Exception as e:
        print(f"대화 품질 테스트 오류: {e}")
        results["conversation_quality"] = 0
    
    try:
        results["level_consistency"] = await test_level_consistency()
    except Exception as e:
        print(f"레벨 일관성 테스트 오류: {e}")
        results["level_consistency"] = 0
    
    try:
        results["response_time"] = await test_response_time()
    except Exception as e:
        print(f"응답 시간 테스트 오류: {e}")
        results["response_time"] = 10
    
    try:
        results["multilingual_support"] = await test_multilingual_support()
    except Exception as e:
        print(f"다국어 지원 테스트 오류: {e}")
        results["multilingual_support"] = {}
    
    try:
        results["error_handling"] = await test_error_handling()
    except Exception as e:
        print(f"오류 처리 테스트 오류: {e}")
        results["error_handling"] = 0
    
    try:
        results["memory_usage"] = await test_memory_usage()
    except Exception as e:
        print(f"메모리 사용량 테스트 오류: {e}")
        results["memory_usage"] = {"memory_efficiency": 0.5}
    
    # 종합 평가
    print("\n" + "=" * 60)
    print("종합 평가")
    print("=" * 60)
    
    scores = {
        "대화 품질": results.get("conversation_quality", 0),
        "레벨 일관성": results.get("level_consistency", 0),
        "응답 속도": 1.0 if results.get("response_time", 10) < 2.0 else 0.5,
        "다국어 지원": len([r for r in results.get("multilingual_support", {}).values() if r.get("level_test")]) / 5,
        "오류 처리": results.get("error_handling", 0),
        "메모리 효율성": results.get("memory_usage", {}).get("memory_efficiency", 0)
    }
    
    for category, score in scores.items():
        grade = "우수" if score >= 0.8 else "양호" if score >= 0.6 else "개선필요"
        print(f"{category:12}: {score:.2f} ({grade})")
    
    overall_score = sum(scores.values()) / len(scores)
    overall_grade = "우수" if overall_score >= 0.8 else "양호" if overall_score >= 0.6 else "개선필요"
    
    print(f"\n종합 점수: {overall_score:.2f} ({overall_grade})")
    
    # 개선 권장사항
    print("\n개선 권장사항:")
    if scores["대화 품질"] < 0.7:
        print("- 대화 AI의 컨텍스트 이해 능력 향상 필요")
    if scores["레벨 일관성"] < 0.7:
        print("- 레벨 테스트 알고리즘의 안정성 개선 필요")
    if scores["응답 속도"] < 0.7:
        print("- 시스템 성능 최적화 및 캐싱 전략 필요")
    if scores["다국어 지원"] < 0.7:
        print("- 다국어 지원 기능 확장 및 안정화 필요")
    if scores["오류 처리"] < 0.7:
        print("- 예외 처리 로직 강화 및 사용자 피드백 개선 필요")
    if scores["메모리 효율성"] < 0.7:
        print("- 메모리 관리 최적화 및 세션 정리 개선 필요")
    
    if overall_score >= 0.8:
        print("- 전반적으로 우수한 성능입니다. 현재 수준을 유지하세요.")
    
    return results

if __name__ == "__main__":
    asyncio.run(run_detailed_tests())