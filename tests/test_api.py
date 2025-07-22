# test_api.py - FastAPI 서버 테스트

import requests
import json
import base64
import time
import asyncio
import websockets
from datetime import datetime

# API 기본 URL
BASE_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000"

def test_basic_endpoints():
    """기본 엔드포인트 테스트"""
    
    print("🔍 기본 API 엔드포인트 테스트...")
    
    # 1. 루트 엔드포인트
    try:
        response = requests.get(f"{BASE_URL}/")
        print(f"✅ GET / : {response.status_code}")
        print(f"   응답: {response.json()['message']}")
    except Exception as e:
        print(f"❌ GET / 실패: {e}")
    
    # 2. 헬스체크
    try:
        response = requests.get(f"{BASE_URL}/health")
        data = response.json()
        print(f"✅ GET /health : {response.status_code}")
        print(f"   상태: {'정상' if data['healthy'] else '비정상'}")
        for service, status in data['services'].items():
            print(f"   - {service}: {'✅' if status else '❌'}")
    except Exception as e:
        print(f"❌ GET /health 실패: {e}")
    
    # 3. 지원 상황 목록
    try:
        response = requests.get(f"{BASE_URL}/api/situations")
        data = response.json()
        print(f"✅ GET /api/situations : {response.status_code}")
        print(f"   총 시나리오: {data['total_scenarios']}개")
        for situation, info in data['situations'].items():
            print(f"   - {info['name']}: {info['scenario_count']}개")
    except Exception as e:
        print(f"❌ GET /api/situations 실패: {e}")
    
    # 4. 지원 언어 목록
    try:
        response = requests.get(f"{BASE_URL}/api/languages")
        data = response.json()
        print(f"✅ GET /api/languages : {response.status_code}")
        print(f"   지원 언어: {', '.join(data['common_languages'])}")
    except Exception as e:
        print(f"❌ GET /api/languages 실패: {e}")

def test_conversation_flow():
    """대화 흐름 테스트"""
    
    print("\n💬 대화 흐름 API 테스트...")
    
    session_id = None
    
    # 1. 대화 시작
    try:
        start_data = {
            "user_id": "test_user_123",
            "situation": "airport",
            "difficulty": "beginner",
            "language": "en"
        }
        
        response = requests.post(f"{BASE_URL}/api/conversation/start", json=start_data)
        data = response.json()
        
        if response.status_code == 200 and data['success']:
            session_id = data['data']['session_id']
            print(f"✅ 대화 시작 성공!")
            print(f"   세션 ID: {session_id}")
            print(f"   상황: {data['data']['situation']}")
            print(f"   AI 메시지: {data['data']['ai_message']}")
        else:
            print(f"❌ 대화 시작 실패: {data.get('error', '알 수 없는 오류')}")
            return
            
    except Exception as e:
        print(f"❌ 대화 시작 요청 실패: {e}")
        return
    
    # 2. 세션 상태 확인
    try:
        response = requests.get(f"{BASE_URL}/api/conversation/{session_id}/status")
        data = response.json()
        
        if response.status_code == 200:
            print(f"✅ 세션 상태 조회 성공!")
            status = data['status']
            if status['exists']:
                print(f"   진행: {status['current_step']}/{status['total_steps']}")
                print(f"   응답 수: {status['responses_count']}")
        else:
            print(f"❌ 세션 상태 조회 실패")
            
    except Exception as e:
        print(f"❌ 세션 상태 조회 오류: {e}")
    
    # 3. 텍스트 메시지 전송
    test_messages = [
        "I need to check in",
        "Here you are",
        "Thank you"
    ]
    
    for i, message in enumerate(test_messages):
        try:
            message_data = {
                "session_id": session_id,
                "message": message,
                "language": "en"
            }
            
            print(f"\n📝 메시지 {i+1}: '{message}'")
            response = requests.post(f"{BASE_URL}/api/conversation/text", json=message_data)
            data = response.json()
            
            if response.status_code == 200 and data['success']:
                result = data['data']
                print(f"✅ 메시지 처리 성공!")
                print(f"   AI 응답: {result['ai_message']}")
                print(f"   피드백: {result['feedback']['level']} - {result['feedback']['message']}")
                
                if result['completed']:
                    print(f"🎉 시나리오 완료!")
                    summary = result['summary']
                    print(f"   총 응답: {summary['total_responses']}")
                    print(f"   평균 정확도: {summary['average_accuracy']}")
                    break
                else:
                    print(f"   진행: {result['step']}/{result['total_steps']}")
                    
            else:
                print(f"❌ 메시지 처리 실패: {data.get('error', '알 수 없는 오류')}")
                
        except Exception as e:
            print(f"❌ 메시지 전송 오류: {e}")
            
        # 잠시 대기
        time.sleep(1)
    
    # 4. 세션 종료
    try:
        response = requests.delete(f"{BASE_URL}/api/conversation/{session_id}")
        data = response.json()
        
        if response.status_code == 200 and data['success']:
            print(f"\n✅ 세션 종료 성공!")
        else:
            print(f"❌ 세션 종료 실패")
            
    except Exception as e:
        print(f"❌ 세션 종료 오류: {e}")

def test_voice_api():
    """음성 API 테스트 (가상의 오디오 데이터 사용)"""
    
    print("\n🎤 음성 API 테스트...")
    
    # 실제 프로젝트에서는 실제 오디오 파일을 사용해야 함
    # 여기서는 테스트용 더미 데이터 사용
    try:
        # 1. 대화 시작
        start_data = {
            "user_id": "voice_test_user",
            "situation": "restaurant",
            "difficulty": "beginner",
            "language": "en"
        }
        
        response = requests.post(f"{BASE_URL}/api/conversation/start", json=start_data)
        if response.status_code != 200:
            print("❌ 음성 테스트용 대화 시작 실패")
            return
            
        session_id = response.json()['data']['session_id']
        print(f"✅ 음성 테스트용 세션 시작: {session_id}")
        
        # 2. 테스트용 더미 오디오 데이터 (실제로는 WAV 파일 데이터)
        dummy_audio = b"dummy audio data for testing"
        audio_base64 = base64.b64encode(dummy_audio).decode('utf-8')
        
        voice_data = {
            "session_id": session_id,
            "audio_base64": audio_base64,
            "language": "en-US"
        }
        
        print("📢 음성 메시지 전송 (더미 데이터)...")
        response = requests.post(f"{BASE_URL}/api/conversation/voice", json=voice_data)
        
        # 실제 STT 서비스가 더미 데이터를 처리할 수 없으므로 400 오류 예상
        if response.status_code == 400:
            print("✅ 음성 API 엔드포인트 정상 작동 (STT 실패는 예상된 결과)")
        else:
            print(f"⚠️ 예상과 다른 응답: {response.status_code}")
            
    except Exception as e:
        print(f"❌ 음성 API 테스트 오류: {e}")

async def test_websocket():
    """WebSocket 실시간 통신 테스트"""
    
    print("\n🔌 WebSocket 테스트...")
    
    try:
        # WebSocket 연결
        uri = f"{WS_URL}/ws/conversation/websocket_test_session"
        
        async with websockets.connect(uri) as websocket:
            print("✅ WebSocket 연결 성공!")
            
            # 1. Ping 테스트
            ping_message = {
                "type": "ping",
                "timestamp": datetime.now().isoformat()
            }
            
            await websocket.send(json.dumps(ping_message))
            print("📤 Ping 메시지 전송")
            
            # Pong 응답 수신
            response = await websocket.recv()
            data = json.loads(response)
            
            if data.get("type") == "pong":
                print("✅ Pong 응답 수신 성공!")
            else:
                print(f"⚠️ 예상과 다른 응답: {data}")
            
            # 2. 텍스트 메시지 테스트
            text_message = {
                "type": "text",
                "text": "Hello, I need help with directions"
            }
            
            await websocket.send(json.dumps(text_message))
            print("📤 텍스트 메시지 전송")
            
            # 응답 수신
            response = await websocket.recv()
            data = json.loads(response)
            
            if data.get("type") == "text_response":
                print("✅ 텍스트 응답 수신 성공!")
                print(f"   AI 응답: {data['data'].get('ai_message', 'N/A')}")
            else:
                print(f"⚠️ 예상과 다른 응답 타입: {data.get('type', 'unknown')}")
            
            print("✅ WebSocket 테스트 완료!")
            
    except websockets.exceptions.ConnectionClosed:
        print("❌ WebSocket 연결이 닫혔습니다")
    except Exception as e:
        print(f"❌ WebSocket 테스트 오류: {e}")

def test_error_handling():
    """오류 처리 테스트"""
    
    print("\n🚨 오류 처리 테스트...")
    
    # 1. 존재하지 않는 세션 조회
    try:
        response = requests.get(f"{BASE_URL}/api/conversation/nonexistent_session/status")
        print(f"✅ 존재하지 않는 세션 조회: {response.status_code}")
        
    except Exception as e:
        print(f"❌ 세션 조회 테스트 오류: {e}")
    
    # 2. 잘못된 상황으로 대화 시작
    try:
        invalid_data = {
            "user_id": "test_user",
            "situation": "invalid_situation",
            "difficulty": "beginner",
            "language": "en"
        }
        
        response = requests.post(f"{BASE_URL}/api/conversation/start", json=invalid_data)
        print(f"✅ 잘못된 상황 테스트: {response.status_code}")
        
        if response.status_code == 400:
            print("   적절한 400 오류 응답")
        
    except Exception as e:
        print(f"❌ 잘못된 상황 테스트 오류: {e}")
    
    # 3. 빈 메시지 전송
    try:
        empty_message = {
            "session_id": "test_session",
            "message": "",
            "language": "en"
        }
        
        response = requests.post(f"{BASE_URL}/api/conversation/text", json=empty_message)
        print(f"✅ 빈 메시지 테스트: {response.status_code}")
        
    except Exception as e:
        print(f"❌ 빈 메시지 테스트 오류: {e}")

def test_load_performance():
    """부하 테스트 (간단한 버전)"""
    
    print("\n⚡ 간단한 성능 테스트...")
    
    # 여러 개의 동시 대화 세션 생성
    sessions = []
    start_time = time.time()
    
    for i in range(5):  # 5개 세션
        try:
            start_data = {
                "user_id": f"load_test_user_{i}",
                "situation": "airport",
                "difficulty": "beginner",
                "language": "en"
            }
            
            response = requests.post(f"{BASE_URL}/api/conversation/start", json=start_data)
            
            if response.status_code == 200:
                session_id = response.json()['data']['session_id']
                sessions.append(session_id)
                print(f"✅ 세션 {i+1} 생성: {session_id[:20]}...")
            else:
                print(f"❌ 세션 {i+1} 생성 실패")
                
        except Exception as e:
            print(f"❌ 세션 {i+1} 생성 오류: {e}")
    
    creation_time = time.time() - start_time
    print(f"📊 {len(sessions)}개 세션 생성 시간: {creation_time:.2f}초")
    
    # 각 세션에 메시지 전송
    message_start_time = time.time()
    successful_messages = 0
    
    for i, session_id in enumerate(sessions):
        try:
            message_data = {
                "session_id": session_id,
                "message": f"Test message {i+1}",
                "language": "en"
            }
            
            response = requests.post(f"{BASE_URL}/api/conversation/text", json=message_data)
            
            if response.status_code == 200:
                successful_messages += 1
            
        except Exception as e:
            print(f"❌ 메시지 {i+1} 전송 오류: {e}")
    
    message_time = time.time() - message_start_time
    print(f"📊 {successful_messages}개 메시지 처리 시간: {message_time:.2f}초")
    print(f"📊 평균 응답 시간: {message_time/max(successful_messages, 1):.3f}초")
    
    # 세션 정리
    for session_id in sessions:
        try:
            requests.delete(f"{BASE_URL}/api/conversation/{session_id}")
        except:
            pass
    
    print("✅ 성능 테스트 완료!")

def main():
    """메인 테스트 실행"""
    
    print("🚀 FastAPI 서버 테스트 시작!")
    print("=" * 60)
    print("⚠️  서버가 실행 중인지 확인하세요: python app/main.py")
    print("=" * 60)
    
    # 서버 연결 확인
    try:
        response = requests.get(f"{BASE_URL}/", timeout=5)
        if response.status_code == 200:
            print("✅ 서버 연결 확인됨")
        else:
            print(f"❌ 서버 응답 오류: {response.status_code}")
            return
    except requests.exceptions.ConnectionError:
        print("❌ 서버에 연결할 수 없습니다!")
        print("💡 다음 명령으로 서버를 시작하세요:")
        print("   cd app && python main.py")
        return
    except Exception as e:
        print(f"❌ 서버 연결 테스트 오류: {e}")
        return
    
    try:
        # 1. 기본 엔드포인트 테스트
        test_basic_endpoints()
        
        # 2. 대화 흐름 테스트
        test_conversation_flow()
        
        # 3. 음성 API 테스트
        test_voice_api()
        
        # 4. WebSocket 테스트
        print("\n🔌 WebSocket 테스트 실행...")
        asyncio.run(test_websocket())
        
        # 5. 오류 처리 테스트
        test_error_handling()
        
        # 6. 성능 테스트
        test_load_performance()
        
        print("\n🎉 모든 API 테스트 완료!")
        print("\n📖 API 문서 확인: http://localhost:8000/docs")
        print("🔧 Swagger UI: http://localhost:8000/redoc")
        
    except KeyboardInterrupt:
        print("\n⏹️ 테스트가 중단되었습니다.")
    except Exception as e:
        print(f"\n❌ 테스트 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()