# analyze_data_structure.py - 수집된 데이터 구조 분석

import json
import os

def analyze_collected_data():
    """수집된 데이터의 실제 구조 분석"""
    
    json_file = 'free_travel_conversations_en_20250722_161841.json'
    
    if not os.path.exists(json_file):
        print(f"❌ 파일을 찾을 수 없습니다: {json_file}")
        return
    
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print("📊 데이터 구조 분석 결과:")
        print("=" * 50)
        
        # 전체 구조 확인
        print(f"✅ 최상위 키들: {list(data.keys())}")
        
        if 'metadata' in data:
            metadata = data['metadata']
            print(f"📋 메타데이터:")
            for key, value in metadata.items():
                print(f"   - {key}: {value}")
        
        if 'conversations' in data:
            conversations = data['conversations']
            print(f"\n💬 대화 데이터:")
            print(f"   총 대화 수: {len(conversations)}")
            
            # 첫 번째 대화 구조 확인
            if conversations:
                first_conv = conversations[0]
                print(f"\n📝 첫 번째 대화 예시:")
                for key, value in first_conv.items():
                    if isinstance(value, str) and len(value) > 100:
                        print(f"   - {key}: {value[:100]}...")
                    else:
                        print(f"   - {key}: {value}")
                
                # 상황별 분포 확인
                situation_count = {}
                dialogue_lengths = []
                
                for conv in conversations:
                    situation = conv.get('situation', 'unknown')
                    situation_count[situation] = situation_count.get(situation, 0) + 1
                    
                    dialogue = conv.get('dialogue', '')
                    dialogue_lengths.append(len(dialogue))
                
                print(f"\n📊 상황별 분포:")
                for situation, count in situation_count.items():
                    print(f"   - {situation}: {count}개")
                
                avg_length = sum(dialogue_lengths) / len(dialogue_lengths) if dialogue_lengths else 0
                print(f"\n📏 대화 길이 통계:")
                print(f"   - 평균 길이: {avg_length:.1f} 문자")
                print(f"   - 최소 길이: {min(dialogue_lengths)} 문자")
                print(f"   - 최대 길이: {max(dialogue_lengths)} 문자")
                
                # 샘플 대화 내용 확인
                print(f"\n🔍 샘플 대화 내용들:")
                for i, conv in enumerate(conversations[:3]):
                    print(f"\n   샘플 {i+1} ({conv.get('situation', 'unknown')}):")
                    dialogue = conv.get('dialogue', '')[:200]
                    print(f"   \"{dialogue}...\"")
                    
                    # 소스 정보 확인
                    source = conv.get('source', 'unknown')
                    print(f"   소스: {source}")
        
    except Exception as e:
        print(f"❌ 데이터 분석 중 오류: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    analyze_collected_data()