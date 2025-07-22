# test_stt_tts.py - STT/TTS 테스트 스크립트

import asyncio
import sys
import os

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 현재 프로젝트 구조에 맞게 import 경로 수정
try:
    from app.services.speech_recognition_service import stt_service
    from app.services.text_to_speech_service import tts_service
except ImportError:
    print("❌ app.services 모듈을 찾을 수 없습니다!")
    print("💡 다음을 확인하세요:")
    print("1. app/services/ 폴더가 있는지 확인")
    print("2. app/services/__init__.py 파일이 있는지 확인") 
    print("3. app/services/speech_recognition_service.py 파일이 있는지 확인")
    print("4. app/services/text_to_speech_service.py 파일이 있는지 확인")
    sys.exit(1)

async def test_tts_only():
    """TTS만 테스트 (음성 인식 없이)"""
    
    print("🔊 TTS (텍스트 → 음성) 테스트 시작...")
    
    # 테스트할 텍스트들
    test_texts = {
        "ko": "안녕하세요! 여행 영어 학습 앱입니다.",
        "en": "Hello! Welcome to our travel English learning app.",
    }
    
    for lang, text in test_texts.items():
        print(f"\n📝 테스트 텍스트 ({lang}): {text}")
        
        # TTS 변환
        audio_base64 = await tts_service.text_to_speech_base64(
            text=text,
            language=lang,
            speed=150,
            volume=0.9
        )
        
        if audio_base64:
            print(f"✅ TTS 성공! Base64 길이: {len(audio_base64)} 문자")
            
            # Base64를 WAV 파일로 저장해서 재생 가능하게 만들기
            import base64
            audio_data = base64.b64decode(audio_base64)
            
            output_file = f"test_output_{lang}.wav"
            with open(output_file, 'wb') as f:
                f.write(audio_data)
            
            print(f"💾 음성 파일 저장: {output_file}")
            print(f"🎵 파일을 재생해서 음성을 확인해보세요!")
        else:
            print(f"❌ TTS 실패")

async def test_tts_voice_info():
    """사용 가능한 음성 정보 확인"""
    
    print("\n🎤 시스템 음성 정보 조회...")
    
    voice_info = await tts_service.get_voice_info()
    
    if voice_info:
        print(f"현재 음성 속도: {voice_info.get('rate')}")
        print(f"현재 볼륨: {voice_info.get('volume')}")
        print(f"사용 가능한 음성 개수: {len(voice_info.get('available_voices', []))}")
        
        print("\n📋 사용 가능한 음성들:")
        for i, voice in enumerate(voice_info.get('available_voices', [])[:5]):  # 처음 5개만
            print(f"  {i+1}. {voice.get('name')} (언어: {voice.get('language')})")
    else:
        print("❌ 음성 정보 조회 실패")

async def test_stt_simple():
    """간단한 STT 테스트 (이미 있는 음성 파일 사용)"""
    
    print("\n🎤 STT (음성 → 텍스트) 테스트...")
    
    # 지원 언어 확인
    supported_langs = stt_service.get_supported_languages()
    print(f"🌍 지원 언어: {list(supported_langs.keys())}")
    
    # 테스트용 더미 Base64 (실제로는 음성 파일이 있어야 함)
    print("💡 실제 음성 파일이 있다면 STT 테스트가 가능합니다.")
    print("   - 음성 파일을 Base64로 변환해서 테스트하거나")
    print("   - 마이크 테스트를 실행하세요")

async def test_microphone_stt():
    """마이크로 실시간 STT 테스트"""
    
    print("\n🎙️ 마이크 STT 테스트...")
    print("⚠️  주의: 마이크 권한이 필요합니다!")
    
    choice = input("마이크 테스트를 진행하시겠습니까? (y/n): ")
    
    if choice.lower() == 'y':
        print("🔴 5초간 말씀해주세요...")
        
        try:
            # 한국어로 음성 인식
            result = await stt_service.recognize_from_microphone(
                language="ko-KR",
                timeout=5
            )
            
            if result:
                print(f"✅ 인식된 텍스트: {result}")
                
                # 인식된 텍스트를 다시 TTS로 변환
                print("🔄 인식된 텍스트를 음성으로 변환 중...")
                audio_base64 = await tts_service.text_to_speech_base64(
                    text=result,
                    language="ko"
                )
                
                if audio_base64:
                    import base64
                    audio_data = base64.b64decode(audio_base64)
                    with open("stt_result.wav", 'wb') as f:
                        f.write(audio_data)
                    print("💾 결과 음성 저장: stt_result.wav")
                
            else:
                print("❌ 음성 인식 실패")
                
        except Exception as e:
            print(f"❌ 마이크 테스트 오류: {e}")
            print("💡 마이크가 연결되어 있고 권한이 허용되었는지 확인하세요")
    else:
        print("👋 마이크 테스트를 건너뜁니다")

async def main():
    """메인 테스트 실행"""
    
    print("🚀 STT/TTS 서비스 테스트 시작!")
    print("=" * 50)
    
    try:
        # 1. TTS 테스트 (가장 기본)
        await test_tts_only()
        
        # 2. 음성 정보 확인
        await test_tts_voice_info()
        
        # 3. STT 간단 테스트
        await test_stt_simple()
        
        # 4. 마이크 테스트 (선택사항)
        await test_microphone_stt()
        
        print("\n🎉 모든 테스트 완료!")
        print("💡 생성된 WAV 파일들을 재생해서 음성을 확인해보세요!")
        
    except ImportError as e:
        print(f"❌ 라이브러리 import 오류: {e}")
        print("💡 필요한 라이브러리를 설치해주세요:")
        print("   pip install speechrecognition pyttsx3 sounddevice")
        
    except Exception as e:
        print(f"❌ 테스트 중 오류 발생: {e}")

if __name__ == "__main__":
    # 비동기 실행
    asyncio.run(main())