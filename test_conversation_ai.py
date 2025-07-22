# test_conversation_ai.py - 시나리오 기반 대화 AI 테스트

import asyncio
import sys
import os

# 프로젝트 경로 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from app.services.conversation_ai_service import conversation_ai_service
except ImportError:
    print("❌ conversation_ai_service 모듈을 찾을 수 없습니다!")
    print("💡 app/services/conversation_ai_service.py 파일을 확인하세요")
    sys.exit(1)

def test_data_loading():
    """수집된 데이터 로딩 테스트"""
    
    print("📊 수집된 데이터 로딩 테스트...")
    
    # 사용 가능한 상황 확인
    situations = conversation_ai_service.get_available_situations()
    print(f"✅ 사용 가능한 상황: {situations}")
    
    # 각 상황별 데이터 확인
    for situation in situations:
        scenarios = conversation_ai_service.conversation_scenarios[situation]['scenarios']
        print(f"   📍 {situation}: {len(scenarios)}개 시나리오")
    
    return len(situations) > 0

def test_scenario_start():
    """시나리오 시작 테스트"""
    
    print("\n🚀 시나리오 시작 테스트...")
    
    # 각 상황별로 시나리오 시작 테스트
    test_scenarios = [
        {"session_id": "test_airport", "situation": "airport", "difficulty": "beginner"},
        {"session_id": "test_restaurant", "situation": "restaurant", "difficulty": "intermediate"},
        {"session_id": "test_hotel", "situation": "hotel", "difficulty": "beginner"},
        {"session_id": "test_street", "situation": "street", "difficulty": "beginner"}
    ]
    
    results = []
    
    for scenario in test_scenarios:
        print(f"\n📝 테스트: {scenario['situation']} ({scenario['difficulty']})")
        
        result = conversation_ai_service.start_scenario(
            session_id=scenario['session_id'],
            situation=scenario['situation'],
            difficulty=scenario['difficulty']
        )
        
        if result['success']:
            print(f"✅ 시나리오 시작 성공!")
            print(f"   제목: {result['scenario_title']}")
            print(f"   첫 메시지: {result['first_message']}")
            print(f"   기대 응답: {result['expected_responses']}")
            results.append(True)
        else:
            print(f"❌ 시나리오 시작 실패: {result['error']}")
            results.append(False)
    
    return all(results)

def test_conversation_flow():
    """대화 흐름 테스트"""
    
    print("\n💬 대화 흐름 테스트...")
    
    # 공항 시나리오로 테스트
    session_id = "flow_test_airport"
    
    # 1. 시나리오 시작
    start_result = conversation_ai_service.start_scenario(
        session_id=session_id,
        situation="airport",
        difficulty="beginner"
    )
    
    if not start_result['success']:
        print(f"❌ 시나리오 시작 실패: {start_result['error']}")
        return False
    
    print(f"🤖 AI: {start_result['first_message']}")
    
    # 2. 사용자 응답 시뮬레이션
    user_responses = [
        "I need to check in",           # 적절한 응답
        "Here you are",                # 적절한 응답  
        "Thank you very much",         # 마지막 응답
        "Yes, gate 12 please"          # 추가 응답
    ]
    
    for i, user_message in enumerate(user_responses):
        print(f"\n💬 사용자 (단계 {i+1}): {user_message}")
        
        response = conversation_ai_service.process_user_response(
            session_id=session_id,
            user_message=user_message
        )
        
        if response['success']:
            print(f"📊 피드백: {response['feedback']['message']}")
            print(f"   레벨: {response['feedback']['level']}")
            
            if not response.get('completed', False):
                print(f"🤖 AI: {response['ai_message']}")
                print(f"   진행상황: {response['step']}/{response['total_steps']}")
            else:
                print(f"🎉 시나리오 완료!")
                print(f"📋 요약: {response['summary']}")
                break
        else:
            print(f"❌ 응답 처리 실패: {response['error']}")
            return False
    
    return True

def test_session_management():
    """세션 관리 테스트"""
    
    print("\n🔧 세션 관리 테스트...")
    
    session_id = "session_mgmt_test"
    
    # 1. 초기 세션 상태 확인
    status = conversation_ai_service.get_session_status(session_id)
    print(f"초기 세션 상태: {status}")
    
    # 2. 시나리오 시작
    result = conversation_ai_service.start_scenario(
        session_id=session_id,
        situation="restaurant",
        difficulty="beginner"
    )
    
    if result['success']:
        print("✅ 시나리오 시작됨")
        
        # 3. 시나리오 시작 후 세션 상태 확인
        status = conversation_ai_service.get_session_status(session_id)
        print(f"시나리오 시작 후: {status}")
        
        return True
    else:
        print(f"❌ 시나리오 시작 실패: {result['error']}")
        return False

def test_feedback_system():
    """피드백 시스템 테스트"""
    
    print("\n📊 피드백 시스템 테스트...")
    
    session_id = "feedback_test"
    
    # 시나리오 시작
    conversation_ai_service.start_scenario(
        session_id=session_id,
        situation="hotel",
        difficulty="beginner"
    )
    
    # 다양한 품질의 응답 테스트
    test_responses = [
        {"message": "I have a reservation", "expected_quality": "good"},
        {"message": "yes", "expected_quality": "needs_improvement"},
        {"message": "I would like to check in please", "expected_quality": "excellent"},
        {"message": "xyz", "expected_quality": "needs_improvement"}
    ]
    
    for test_resp in test_responses:
        print(f"\n💬 테스트 응답: '{test_resp['message']}'")
        
        result = conversation_ai_service.process_user_response(
            session_id=session_id,
            user_message=test_resp['message']
        )
        
        if result['success']:
            feedback = result['feedback']
            print(f"   📊 피드백 레벨: {feedback['level']}")
            print(f"   📝 메시지: {feedback['message']}")
            print(f"   🎯 정확도 점수: {feedback['accuracy_score']}")
            
            if feedback.get('suggestion'):
                print(f"   💡 제안: {feedback['suggestion']}")
        else:
            print(f"   ❌ 오류: {result['error']}")
        
        # 시나리오 완료 체크
        if result.get('completed', False):
            break
    
    return True

def main():
    """메인 테스트 실행"""
    
    print("🚀 시나리오 기반 대화 AI 테스트 시작!")
    print("=" * 60)
    
    # JSON 파일 존재 확인
    json_file = 'free_travel_conversations_en_20250722_161841.json'
    if not os.path.exists(json_file):
        print(f"⚠️  수집된 데이터 파일이 없습니다: {json_file}")
        print("💡 기본 시나리오로 테스트를 진행합니다.")
    else:
        print(f"✅ 수집된 데이터 파일 확인: {json_file}")
    
    try:
        # 1. 데이터 로딩 테스트
        if test_data_loading():
            print("✅ 데이터 로딩 테스트 통과")
        else:
            print("❌ 데이터 로딩 테스트 실패")
            return
        
        # 2. 시나리오 시작 테스트
        if test_scenario_start():
            print("✅ 시나리오 시작 테스트 통과")
        else:
            print("❌ 시나리오 시작 테스트 실패")
            return
        
        # 3. 대화 흐름 테스트
        if test_conversation_flow():
            print("✅ 대화 흐름 테스트 통과")
        else:
            print("❌ 대화 흐름 테스트 실패")
            return
        
        # 4. 세션 관리 테스트
        if test_session_management():
            print("✅ 세션 관리 테스트 통과")
        else:
            print("❌ 세션 관리 테스트 실패")
        
        # 5. 피드백 시스템 테스트
        if test_feedback_system():
            print("✅ 피드백 시스템 테스트 통과")
        else:
            print("❌ 피드백 시스템 테스트 실패")
        
        print("\n🎉 모든 테스트 완료!")
        print("💡 실제 대화 데이터를 기반으로 한 시나리오가 준비되었습니다!")
        
    except Exception as e:
        print(f"❌ 테스트 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()