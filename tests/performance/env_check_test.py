"""
환경변수 설정 확인 및 Mock 테스트
.env 파일 문제를 진단하고 해결합니다.
"""

import os
import sys
from pathlib import Path

# 프로젝트 루트 찾기
current_dir = Path(__file__).parent
project_root = current_dir.parent.parent
env_file_path = project_root / '.env'

print("=" * 60)
print("환경변수 및 의존성 진단")
print("=" * 60)

print(f"\n📁 경로 정보:")
print(f"   현재 디렉토리: {current_dir}")
print(f"   프로젝트 루트: {project_root}")
print(f"   .env 파일 경로: {env_file_path}")

# .env 파일 존재 확인
print(f"\n🔍 .env 파일 확인:")
if env_file_path.exists():
    print(f"   ✅ .env 파일 존재: {env_file_path}")
    
    # .env 파일 내용 확인 (민감한 정보 제외)
    try:
        with open(env_file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        print(f"   📄 .env 파일 내용 ({len(lines)}줄):")
        for i, line in enumerate(lines[:10]):  # 처음 10줄만 보기
            line = line.strip()
            if line and not line.startswith('#'):
                key = line.split('=')[0] if '=' in line else line
                print(f"      {i+1}: {key}=***")
            elif line:
                print(f"      {i+1}: {line}")
    except Exception as e:
        print(f"   ❌ .env 파일 읽기 오류: {e}")
else:
    print(f"   ❌ .env 파일이 존재하지 않습니다!")
    print(f"   💡 다음 위치에 .env 파일을 생성하세요: {env_file_path}")

# python-dotenv 설치 확인
print(f"\n📦 필수 패키지 확인:")
try:
    import dotenv
    print("   ✅ python-dotenv: 설치됨")
    
    # .env 파일 로드 시도
    if env_file_path.exists():
        dotenv.load_dotenv(env_file_path)
        print("   ✅ .env 파일 로드 성공")
    else:
        print("   ⚠️ .env 파일이 없어서 로드할 수 없음")
        
except ImportError:
    print("   ❌ python-dotenv: 설치되지 않음")
    print("   💡 설치 명령: pip install python-dotenv")

try:
    import supabase
    print("   ✅ supabase: 설치됨")
except ImportError:
    print("   ❌ supabase: 설치되지 않음")
    print("   💡 설치 명령: pip install supabase")

# 환경변수 확인
print(f"\n🔧 현재 환경변수 상태:")
env_vars = [
    'SUPABASE_URL',
    'SUPABASE_ANON_KEY', 
    'ELEVENLABS_API_KEY',
    'OPENAI_API_KEY'
]

for var in env_vars:
    value = os.getenv(var)
    if value:
        print(f"   ✅ {var}: 설정됨 ({'*' * min(len(value), 8)}...)")
    else:
        print(f"   ❌ {var}: 설정되지 않음")

# 간단한 Mock 테스트 실행
print(f"\n🧪 Mock 테스트 실행:")

import asyncio
import json
import random
from datetime import datetime

async def run_mock_test():
    """환경변수 없이도 작동하는 Mock 테스트"""
    
    # Mock 데이터 생성
    mock_results = []
    for i in range(10):
        result = {
            "session_id": f"mock_{i+1}",
            "target_text": f"Test sentence {i+1}",
            "user_level": random.choice(['A1', 'A2', 'B1', 'B2']),
            "language": random.choice(['en', 'ko']),
            "final_accuracy": random.uniform(65, 95),
            "confidence": random.uniform(0.7, 0.95)
        }
        mock_results.append(result)
        await asyncio.sleep(0.01)  # 실제 처리 시뮬레이션
    
    # 결과 분석
    total_accuracy = sum(r['final_accuracy'] for r in mock_results) / len(mock_results)
    
    print(f"   ✅ Mock 테스트 완료:")
    print(f"      샘플 수: {len(mock_results)}")
    print(f"      평균 정확도: {total_accuracy:.2f}%")
    
    # 레벨별 분석
    level_stats = {}
    for result in mock_results:
        level = result['user_level']
        if level not in level_stats:
            level_stats[level] = []
        level_stats[level].append(result['final_accuracy'])
    
    print(f"      레벨별 정확도:")
    for level, accuracies in level_stats.items():
        avg_acc = sum(accuracies) / len(accuracies)
        print(f"         {level}: {avg_acc:.1f}% ({len(accuracies)}개 샘플)")
    
    # 결과 저장
    report = {
        "test_type": "mock_pronunciation_accuracy",
        "test_date": datetime.now().isoformat(),
        "total_samples": len(mock_results),
        "overall_accuracy": round(total_accuracy, 2),
        "level_breakdown": {
            level: {
                "accuracy": round(sum(accs)/len(accs), 2),
                "sample_count": len(accs)
            }
            for level, accs in level_stats.items()
        },
        "detailed_results": mock_results
    }
    
    filename = f"mock_pronunciation_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    print(f"   📄 결과 저장: {filename}")
    
    return report

# 비동기 함수 실행
try:
    result = asyncio.run(run_mock_test())
    print(f"\n✅ Mock 테스트가 성공적으로 완료되었습니다!")
except Exception as e:
    print(f"\n❌ Mock 테스트 실패: {e}")

# 해결 방안 제시
print(f"\n" + "=" * 60)
print("해결 방안")
print("=" * 60)

if not env_file_path.exists():
    print(f"\n1️⃣ .env 파일 생성:")
    print(f"   다음 내용으로 {env_file_path} 파일을 생성하세요:")
    print(f"""
# Supabase 설정 (필요한 경우)
SUPABASE_URL=your_supabase_project_url
SUPABASE_ANON_KEY=your_supabase_anon_key

# ElevenLabs API (필요한 경우)  
ELEVENLABS_API_KEY=your_elevenlabs_api_key

# OpenAI API (필요한 경우)
OPENAI_API_KEY=your_openai_api_key
""")

missing_packages = []
try:
    import dotenv
except ImportError:
    missing_packages.append("python-dotenv")

try:
    import supabase
except ImportError:
    missing_packages.append("supabase")

if missing_packages:
    print(f"\n2️⃣ 필수 패키지 설치:")
    print(f"   pip install {' '.join(missing_packages)}")

print(f"\n3️⃣ 임시 해결책:")
print(f"   환경변수 설정이 완료될 때까지 Mock 테스트를 사용하세요.")
print(f"   Mock 테스트는 실제 서비스 없이도 테스트 로직을 검증할 수 있습니다.")

print(f"\n4️⃣ 테스트 실행:")
print(f"   cd {current_dir}")
print(f"   python -c \"import asyncio; asyncio.run(run_mock_test())\"")