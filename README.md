# AI README
## 가상환경 생성
```bash
# Python 3.11.8 설치 확인
python --version

# 가상환경 생성
python -m venv multilingual_ai_env

# 가상환경 활성화
# Windows
source multilingual_ai_env/Scripts/activate
# macOS/Linux
source multilingual_ai_env/bin/activate
```

# 패키지 설치
python -m pip install -r requirements.txt

# 추가 언어 모델 다운로드
```bash
# 1. spaCy 언어 모델 설치
python -m spacy download en_core_web_sm
python -m spacy download ko_core_news_sm
python -m spacy download ja_core_news_sm
python -m spacy download zh_core_web_sm
python -m spacy download es_core_news_sm
python -m spacy download fr_core_news_sm

 # 2. NLTK 데이터 다운로드
python -c "import nltk; nltk.download('punkt'); nltk.download('stopwords')"
```