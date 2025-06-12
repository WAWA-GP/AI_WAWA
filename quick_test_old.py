# 최소한의 Common Voice 영어 테스트
from datasets import load_dataset
from datasets import DownloadConfig

print("🎯 Common Voice 영어(en) 최소 테스트")

my_token = ""  # 본인의 토큰
download_config = DownloadConfig(token=my_token)

try:
    print("📥 데이터셋 로딩 중... (시간이 좀 걸릴 수 있어요)")
    
    # 가장 기본적인 방법
    dataset = load_dataset(
        "mozilla-foundation/common_voice_17_0",
        "en",
        split="train",
        streaming=True,
        download_config=download_config
)
    
    print("✅ 데이터셋 로드 성공!")
    
    # 첫 번째 샘플만 가져오기
    print("📊 첫 번째 샘플 확인 중...")
    sample = next(iter(dataset))
    
    print("🎉 성공! 샘플 데이터:")
    print(f"   텍스트: {sample['sentence']}")
    print(f"   화자 ID: {sample['client_id'][:20]}...")  # ID 일부만 표시
    
    # 오디오 정보
    audio = sample['audio']
    print(f"   샘플링 레이트: {audio['sampling_rate']}Hz")
    print(f"   오디오 길이: {len(audio['array'])} samples")
    print(f"   재생 시간: {len(audio['array'])/audio['sampling_rate']:.2f}초")
    
    # 추가 메타데이터 (있는 경우)
    if 'up_votes' in sample:
        print(f"   좋아요: {sample['up_votes']}")
    if 'down_votes' in sample:
        print(f"   싫어요: {sample['down_votes']}")
    if 'gender' in sample:
        print(f"   성별: {sample['gender']}")
    if 'age' in sample:
        print(f"   나이: {sample['age']}")
    
    print("\n✅ Common Voice 영어 데이터 접근 성공!")
    print("이제 본격적인 다운로드를 시작할 수 있습니다!")
    
except Exception as e:
    print(f"❌ 에러 발생: {e}")
    
    # 구체적인 에러 타입 확인
    error_str = str(e).lower()
    
    if "connection" in error_str:
        print("🌐 인터넷 연결 문제일 수 있습니다.")
    elif "403" in error_str or "unauthorized" in error_str:
        print("🔒 권한 문제입니다. 다시 로그인 해보세요:")
        print("   huggingface-cli login")
    elif "timeout" in error_str:
        print("⏰ 타임아웃 - 잠시 후 다시 시도해보세요.")
    else:
        print("💡 다른 버전을 시도해보세요:")
        print("   mozilla-foundation/common_voice_12_0")
        print("   mozilla-foundation/common_voice_11_0")

print("\n🔄 테스트 완료")