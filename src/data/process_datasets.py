import pandas as pd
import numpy as np
import json
from pathlib import Path
import re

print("🚀 데이터셋 전처리 시작!\n")

# 1. 어휘 데이터 (이미 성공)
print("📚 어휘 데이터는 이미 처리 완료")

# 2. 대화 데이터 - 인코딩 문제 해결
print("\n💬 대화 데이터 처리 중 (인코딩 문제 해결)...")

conv_file = Path("data/raw/conversations/31. Chat(1.7k).csv")
print(f"파일 경로: {conv_file}")

# 여러 인코딩 시도
encodings = ['iso-8859-1', 'latin1', 'cp1252', 'utf-8']
df = None

for encoding in encodings:
    try:
        print(f"인코딩 시도: {encoding}")
        df = pd.read_csv(conv_file, encoding=encoding)
        print(f"✅ {encoding} 인코딩으로 성공!")
        break
    except Exception as e:
        print(f"❌ {encoding} 실패")
        continue

if df is not None:
    print(f"원본 데이터 shape: {df.shape}")
    print(f"컬럼명: {df.columns.tolist()}")
    
    # 텍스트 정제
    df['text'] = df['text'].astype(str).str.strip()
    df = df[df['text'] != 'nan']
    df = df[df['text'] != '']
    df = df[df['text'] != 'text']  # 헤더 중복 제거
    
    # 통계 계산
    df['text_length'] = df['text'].str.len()
    df['word_count'] = df['text'].str.split().str.len()
    
    print(f"정제 후 대화 수: {len(df)}")
    print(f"평균 텍스트 길이: {df['text_length'].mean():.1f} 글자")
    
    # 샘플 확인
    print("\n샘플 대화 데이터 (첫 3개):")
    for i in range(min(3, len(df))):
        text = df.iloc[i]['text']
        preview = text[:100] + "..." if len(text) > 100 else text
        print(f"  {i+1}. {preview}")
    
    # 대화 쌍 생성
    conversation_pairs = []
    for i in range(0, len(df)-1, 2):
        if i+1 < len(df):
            conversation_pairs.append({
                'user_input': df.iloc[i]['text'],
                'ai_response': df.iloc[i+1]['text']
            })
    
    pairs_df = pd.DataFrame(conversation_pairs)
    
    # 저장
    Path("data/processed").mkdir(exist_ok=True)
    pairs_df.to_csv("data/processed/conversation_pairs.csv", index=False, encoding='utf-8')
    
    print(f"✅ 생성된 대화 쌍: {len(pairs_df)}개")
else:
    print("❌ 대화 데이터 처리 실패")

# 3. 문장 데이터 처리
print("\n📝 사실 문장 데이터 처리 중...")

factual_file = Path("data/raw/factual/sentence.txt")

if factual_file.exists():
    print(f"파일 경로: {factual_file}")
    
    sentences_data = []
    with open(factual_file, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            parts = line.strip().split('\t')
            if len(parts) >= 3:
                sentence = parts[0].strip()
                sentences_data.append({
                    'sentence': sentence,
                    'grammar_label': int(parts[1]),
                    'factual_label': int(parts[2]),
                    'word_count': len(sentence.split()),
                    'has_date': bool(re.search(r'\d{4}', sentence)),
                    'sentence_length': len(sentence)
                })
    
    factual_df = pd.DataFrame(sentences_data)
    
    print(f"전체 문장 수: {len(factual_df)}")
    print(f"문법적으로 올바른 문장: {(factual_df['grammar_label'] == 1).sum()}개")
    
    # 샘플 문장
    print("\n샘플 문장들:")
    for i in range(min(3, len(factual_df))):
        print(f"  {i+1}. {factual_df.iloc[i]['sentence']}")
    
    # 문법 체크용 데이터 생성
    grammar_data = []
    for _, row in factual_df.iterrows():
        grammar_data.append({
            'text': row['sentence'],
            'is_correct': row['grammar_label'] == 1,
            'word_count': row['word_count'],
            'has_date': row['has_date']
        })
    
    grammar_df = pd.DataFrame(grammar_data)
    grammar_df.to_csv("data/processed/grammar_sentences.csv", index=False)
    
    print(f"✅ 문법 데이터 저장 완료")
else:
    print("❌ sentence.txt 파일을 찾을 수 없습니다")

print("\n🎯 전처리 완료!")
print("📁 data/processed/ 폴더 확인:")
