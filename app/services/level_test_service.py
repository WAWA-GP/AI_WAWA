"""
API 기반 적응형 언어 레벨 테스트 서비스
- 공식 API 데이터 활용 (Wordnik, GitHub 어휘 목록)
- CEFR 표준 준수 (A1-C2)
- 실시간 난이도 조정
- 다중 소스 검증
"""

import json
import logging
import asyncio
import requests
import random
from datetime import datetime
from typing import Dict, List, Optional
from openai import OpenAI
import os

logger = logging.getLogger(__name__)

# 언어별 기본 어휘 데이터
BASIC_VOCABULARY = {
    "ko": ["안녕하세요", "감사합니다", "죄송합니다", "도와주세요", "얼마예요", "어디예요", "언제", "무엇", "왜", "누구"],
    "en": ["hello", "thank you", "sorry", "help", "how much", "where", "when", "what", "why", "who"],
    "ja": ["こんにちは", "ありがとうございます", "すみません", "手伝って", "いくらですか", "どこですか", "いつ", "何", "なぜ", "誰"],
    "zh": ["你好", "谢谢", "对不起", "帮助", "多少钱", "在哪里", "什么时候", "什么", "为什么", "谁"],
    "fr": ["bonjour", "merci", "désolé", "aide", "combien", "où", "quand", "quoi", "pourquoi", "qui"]
}

# 언어별 문법 템플릿
GRAMMAR_TEMPLATES = {
    "ko": {
        "A1": {
            "template": "저는 _____ 입니다.",
            "options": {"A": "학생", "B": "학생을", "C": "학생이", "D": "학생에"},
            "correct": "A",
            "point": "주격 조사"
        },
        "A2": {
            "template": "어제 친구를 _____.",
            "options": {"A": "만나요", "B": "만났어요", "C": "만날 거예요", "D": "만나고 있어요"},
            "correct": "B",
            "point": "과거 시제"
        }
    },
    "en": {
        "A1": {
            "template": "She _____ to school every day.",
            "options": {"A": "go", "B": "goes", "C": "going", "D": "went"},
            "correct": "B",
            "point": "present_simple_third_person"
        },
        "A2": {
            "template": "Yesterday, I _____ my homework.",
            "options": {"A": "do", "B": "did", "C": "doing", "D": "will do"},
            "correct": "B",
            "point": "past_simple"
        }
    },
    "ja": {
        "A1": {
            "template": "私は学生_____。",
            "options": {"A": "です", "B": "である", "C": "だ", "D": "でした"},
            "correct": "A",
            "point": "丁寧語"
        },
        "A2": {
            "template": "昨日映画を_____。",
            "options": {"A": "見ます", "B": "見ました", "C": "見る", "D": "見て"},
            "correct": "B",
            "point": "過去形"
        }
    },
    "zh": {
        "A1": {
            "template": "我___中国人。",
            "options": {"A": "是", "B": "在", "C": "有", "D": "做"},
            "correct": "A",
            "point": "系动词"
        },
        "A2": {
            "template": "昨天我___了一本书。",
            "options": {"A": "看", "B": "看着", "C": "看了", "D": "在看"},
            "correct": "C",
            "point": "完成体"
        }
    },
    "fr": {
        "A1": {
            "template": "Je _____ étudiant.",
            "options": {"A": "suis", "B": "es", "C": "est", "D": "sommes"},
            "correct": "A",
            "point": "être_conjugation"
        },
        "A2": {
            "template": "Hier, j'_____ au cinéma.",
            "options": {"A": "vais", "B": "suis allé", "C": "irai", "D": "vais aller"},
            "correct": "B",
            "point": "passé_composé"
        }
    }
}

# 언어별 독해 지문
READING_PASSAGES = {
    "ko": {
        "A1": {
            "passage": "저는 마이클이에요. 미국에서 왔어요. 한국어를 공부하고 있어요. 매일 한국어 수업을 들어요. 한국 음식을 좋아해요. 김치찌개가 맛있어요.",
            "question": "마이클은 어느 나라에서 왔어요?",
            "options": {"A": "미국", "B": "영국", "C": "캐나다", "D": "호주"},
            "correct": "A"
        },
        "A2": {
            "passage": "어제 친구와 명동에 갔어요. 쇼핑을 했어요. 옷을 많이 샀어요. 점심으로 불고기를 먹었어요. 정말 맛있었어요. 카페에서 커피도 마셨어요.",
            "question": "어제 점심에 뭘 먹었어요?",
            "options": {"A": "김치찌개", "B": "불고기", "C": "비빔밥", "D": "냉면"},
            "correct": "B"
        }
    },
    "en": {
        "A1": {
            "passage": "Tom is a student. He is 20 years old. He lives in New York. He studies English at university. He likes reading books and playing soccer.",
            "question": "What does Tom like to do?",
            "options": {"A": "Reading and soccer", "B": "Watching TV", "C": "Cooking", "D": "Swimming"},
            "correct": "A"
        }
    },
    "ja": {
        "A1": {
            "passage": "田中さんは会社員です。毎朝8時に家を出て、電車で会社に行きます。昼休みは同僚と一緒に食事をします。",
            "question": "田中さんはいつ家を出ますか？",
            "options": {"A": "7時", "B": "8時", "C": "9時", "D": "10時"},
            "correct": "B"
        }
    },
    "zh": {
        "A1": {
            "passage": "李明是一名学生。他今年22岁，在北京大学学习中文。他每天坐地铁去学校，晚上在图书馆学习。",
            "question": "李明怎么去学校？",
            "options": {"A": "坐地铁", "B": "坐公交", "C": "开车", "D": "骑自行车"},
            "correct": "A"
        }
    },
    "fr": {
        "A1": {
            "passage": "Marie est étudiante à Paris. Elle a 19 ans et étudie le français. Chaque matin, elle prend le métro pour aller à l'université.",
            "question": "Comment Marie va-t-elle à l'université ?",
            "options": {"A": "En métro", "B": "En bus", "C": "En voiture", "D": "À pied"},
            "correct": "A"
        }
    }
}

class QuickStartLanguageAPI:
    """무료 API들을 활용한 언어 데이터 서비스"""
    
    def __init__(self):
        # Wordnik API (무료 키 발급: https://developer.wordnik.com/)
        self.wordnik_key = os.getenv("WORDNIK_API_KEY", "")
        self.wordnik_base = "https://api.wordnik.com/v4"
        
        # 미리 다운로드한 어휘 목록들
        self.vocabulary_cache = {}
        self.is_initialized = False
    
    async def initialize_datasets(self):
        """무료 데이터셋 초기화"""
        if self.is_initialized:
            return
        
        logger.info("📥 무료 어휘 데이터 다운로드 중...")
        
        # 공개 어휘 목록 URL들
        vocab_urls = {
            "common_words": "https://raw.githubusercontent.com/first20hours/google-10000-english/master/20k.txt",
            "oxford_3000": "https://raw.githubusercontent.com/hackergrrl/oxford-3000/master/oxford-3000.json"
        }
        
        for name, url in vocab_urls.items():
            try:
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    if name == "oxford_3000":
                        try:
                            self.vocabulary_cache[name] = response.json()
                        except:
                            # JSON 파싱 실패 시 텍스트로 처리
                            words = response.text.strip().split('\n')
                            self.vocabulary_cache[name] = [word.strip().lower() for word in words if word.strip()]
                    else:
                        words = response.text.strip().split('\n')
                        self.vocabulary_cache[name] = [word.strip().lower() for word in words if word.strip()]
                    
                    logger.info(f"✅ {name}: {len(self.vocabulary_cache[name])} 단어")
                else:
                    logger.warning(f"❌ {name} 다운로드 실패: {response.status_code}")
                    
            except Exception as e:
                logger.error(f"❌ {name} 오류: {e}")
        
        # 기본 어휘 목록이 없으면 하드코딩된 기본값 사용
        if not self.vocabulary_cache.get("common_words"):
            self.vocabulary_cache["common_words"] = [
                "the", "be", "to", "of", "and", "a", "in", "that", "have", "i",
                "it", "for", "not", "on", "with", "he", "as", "you", "do", "at",
                "this", "but", "his", "by", "from", "they", "we", "say", "her", "she",
                "or", "an", "will", "my", "one", "all", "would", "there", "their", "what",
                "important", "beautiful", "difficult", "expensive", "interesting", "necessary",
                "possible", "available", "comfortable", "dangerous", "educational", "professional"
            ]
            logger.info("📝 기본 어휘 목록 사용")
        
        self.is_initialized = True
    
    async def get_word_cefr_level(self, word: str) -> Dict:
        """단어의 CEFR 레벨 결정"""
        
        if not self.is_initialized:
            await self.initialize_datasets()
        
        word = word.lower().strip()
        analysis = {
            "word": word,
            "estimated_level": "B1",
            "confidence": 0.5,
            "rank": 5000
        }
        
        # 빈도 순위 확인
        if "common_words" in self.vocabulary_cache:
            try:
                rank = self.vocabulary_cache["common_words"].index(word) + 1
                analysis["rank"] = rank
                analysis["estimated_level"] = self._rank_to_cefr(rank)
                analysis["confidence"] = 0.8
            except ValueError:
                analysis["rank"] = 20000
                analysis["estimated_level"] = "C2"
        
        # Wordnik API로 추가 정보 (있는 경우)
        if self.wordnik_key:
            wordnik_data = await self._get_wordnik_data(word)
            if wordnik_data:
                analysis["definitions"] = wordnik_data.get("definitions", [])
                analysis["confidence"] = min(analysis["confidence"] + 0.2, 1.0)
        
        return analysis
    
    def _rank_to_cefr(self, rank: int) -> str:
        """빈도 순위를 CEFR 레벨로 변환"""
        if rank <= 500:
            return "A1"
        elif rank <= 1000:
            return "A2"
        elif rank <= 2000:
            return "B1"
        elif rank <= 4000:
            return "B2"
        elif rank <= 8000:
            return "C1"
        else:
            return "C2"
    
    async def _get_wordnik_data(self, word: str) -> Dict:
        """Wordnik API에서 단어 정보 조회"""
        
        if not self.wordnik_key:
            return {}
        
        try:
            def_url = f"{self.wordnik_base}/word.json/{word}/definitions"
            params = {"api_key": self.wordnik_key, "limit": 2}
            
            response = requests.get(def_url, params=params, timeout=5)
            
            if response.status_code == 200:
                definitions = response.json()
                return {
                    "definitions": [d.get("text", "") for d in definitions],
                    "source": "wordnik"
                }
            
            return {}
            
        except Exception as e:
            logger.warning(f"Wordnik API 오류 ({word}): {e}")
            return {}
    
    async def generate_verified_questions(self, level: str, skill: str, count: int = 1) -> List[Dict]:
        """검증된 어휘 기반 문제 생성"""
        
        if not self.is_initialized:
            await self.initialize_datasets()
        
        level_words = await self._get_level_words(level)
        questions = []
        
        for i in range(min(count, len(level_words), 10)):  # 최대 10개
            word = level_words[i]
            
            if skill == "vocabulary":
                question = await self._create_vocab_question(word, level)
            elif skill == "grammar":
                question = await self._create_grammar_question(word, level)
            elif skill == "reading":
                question = await self._create_reading_question(level)
            else:
                question = await self._create_listening_question(level)
            
            questions.append(question)
        
        return questions
    
    async def _get_level_words(self, level: str) -> List[str]:
        """특정 레벨의 단어들 추출"""
        
        if "common_words" not in self.vocabulary_cache:
            return ["important", "necessary", "possible", "available", "comfortable"]
        
        common_words = self.vocabulary_cache["common_words"]
        
        # 레벨별 단어 범위
        ranges = {
            "A1": (0, 500),
            "A2": (500, 1000),
            "B1": (1000, 2000),
            "B2": (2000, 4000),
            "C1": (4000, 8000),
            "C2": (8000, 12000)
        }
        
        start, end = ranges.get(level, (1000, 2000))
        end = min(end, len(common_words))
        
        if start < len(common_words):
            level_words = common_words[start:end]
        else:
            level_words = common_words[-50:]  # 마지막 50개
        
        # 최소 5개는 보장
        if len(level_words) < 5:
            level_words = common_words[-50:] if common_words else ["important", "necessary", "possible"]
        
        return level_words[:50]  # 상위 50개만
    
    async def _create_vocab_question(self, word: str, level: str) -> Dict:
        """어휘 문제 생성"""
        
        word_analysis = await self.get_word_cefr_level(word)
        definitions = word_analysis.get("definitions", [])
        
        if definitions:
            correct_def = definitions[0][:100]  # 너무 길면 자르기
        else:
            # 레벨별 기본 정의
            basic_definitions = {
                "important": "having great significance or value",
                "necessary": "required to be done or present; essential",
                "possible": "able to be done or achieved",
                "available": "able to be used or obtained",
                "comfortable": "giving a feeling of ease or relaxation"
            }
            correct_def = basic_definitions.get(word, f"A word at {level} level")
        
        # 오답 생성
        distractors = [
            "Something completely different",
            "An unrelated concept",
            "Another meaning entirely"
        ]
        
        options = {"A": correct_def}
        for i, distractor in enumerate(distractors, 1):
            options[chr(65 + i)] = distractor  # B, C, D
        
        return {
            "question_id": f"vocab_{level}_{word}_{random.randint(1000, 9999)}",
            "skill": "vocabulary",
            "level": level,
            "question": f"What does '{word}' mean?",
            "options": options,
            "correct_answer": "A",
            "explanation": f"'{word}' means: {correct_def}",
            "word": word,
            "confidence": word_analysis.get("confidence", 0.8),
            "source": "verified_vocabulary"
        }
    
    async def _create_grammar_question(self, word: str, level: str) -> Dict:
        """문법 문제 생성"""
        
        # 레벨별 문법 템플릿
        grammar_templates = {
            "A1": {
                "template": f"She _____ {word} every day.",
                "options": {"A": "uses", "B": "use", "C": "using", "D": "used"},
                "correct": "A",
                "point": "present_simple_third_person"
            },
            "A2": {
                "template": f"Yesterday, I _____ {word}.",
                "options": {"A": "use", "B": "used", "C": "using", "D": "will use"},
                "correct": "B",
                "point": "past_simple"
            },
            "B1": {
                "template": f"I have _____ {word} many times.",
                "options": {"A": "use", "B": "using", "C": "used", "D": "uses"},
                "correct": "C",
                "point": "present_perfect"
            },
            "B2": {
                "template": f"If I _____ {word}, I would be more successful.",
                "options": {"A": "use", "B": "used", "C": "using", "D": "will use"},
                "correct": "B",
                "point": "second_conditional"
            },
            "C1": {
                "template": f"Having _____ {word}, I understood the concept.",
                "options": {"A": "use", "B": "used", "C": "using", "D": "been used"},
                "correct": "B",
                "point": "participle_clauses"
            },
            "C2": {
                "template": f"Were I _____ {word}, things would be different.",
                "options": {"A": "to use", "B": "using", "C": "used", "D": "use"},
                "correct": "A",
                "point": "subjunctive_inversion"
            }
        }
        
        template = grammar_templates.get(level, grammar_templates["B1"])
        
        return {
            "question_id": f"grammar_{level}_{word}_{random.randint(1000, 9999)}",
            "skill": "grammar",
            "level": level,
            "question": template["template"],
            "options": template["options"],
            "correct_answer": template["correct"],
            "explanation": f"This tests {template['point']} grammar rule.",
            "grammar_point": template["point"],
            "target_word": word,
            "source": "grammar_templates"
        }
    
    async def _create_reading_question(self, level: str) -> Dict:
        """읽기 문제 생성"""
        
        reading_passages = {
            "A1": {
                "passage": "Tom is a student. He is 20 years old. He lives in New York. He studies English at university. He likes reading books and playing soccer. He has many friends at school.",
                "question": "What does Tom like to do?",
                "options": {
                    "A": "Reading books and playing soccer",
                    "B": "Watching TV and sleeping",
                    "C": "Cooking and dancing",
                    "D": "Swimming and running"
                },
                "correct": "A"
            },
            "A2": {
                "passage": "Maria works at a restaurant downtown. She starts work at 6 AM and finishes at 3 PM. She serves breakfast and lunch to customers. The restaurant is always busy during rush hours. Maria enjoys talking to different people every day. She earns good tips from friendly customers.",
                "question": "When does Maria finish work?",
                "options": {"A": "6 AM", "B": "3 PM", "C": "5 PM", "D": "8 PM"},
                "correct": "B"
            },
            "B1": {
                "passage": "Climate change has become one of the most pressing issues of our time. Scientists around the world are working to understand its causes and effects. Many governments have started implementing policies to reduce carbon emissions. However, individual actions are also crucial in addressing this global challenge. Simple changes like using public transportation or recycling can make a difference.",
                "question": "According to the passage, what is crucial in addressing climate change?",
                "options": {
                    "A": "Only government policies",
                    "B": "Only scientific research",
                    "C": "Both government policies and individual actions",
                    "D": "Neither policies nor individual actions"
                },
                "correct": "C"
            },
            "B2": {
                "passage": "The digital revolution has fundamentally transformed how businesses operate in the modern economy. Companies that have successfully adapted to technological changes have gained significant competitive advantages. E-commerce platforms have revolutionized retail, while remote work technologies have redefined traditional office environments. Organizations must continuously evolve their strategies to remain relevant in this rapidly changing landscape.",
                "question": "What gives companies competitive advantages according to the passage?",
                "options": {
                    "A": "Having traditional office environments",
                    "B": "Successfully adapting to technological changes",
                    "C": "Avoiding digital transformation",
                    "D": "Maintaining old business strategies"
                },
                "correct": "B"
            },
            "C1": {
                "passage": "Contemporary neuroscience research has revealed fascinating insights into the plasticity of the human brain. Neuroplasticity refers to the brain's remarkable ability to reorganize itself by forming new neural connections throughout life. This discovery has profound implications for rehabilitation medicine, educational practices, and our understanding of cognitive development. The brain's capacity for adaptation challenges previously held beliefs about fixed cognitive abilities.",
                "question": "What does neuroplasticity challenge according to the passage?",
                "options": {
                    "A": "The brain's ability to reorganize",
                    "B": "Previously held beliefs about fixed cognitive abilities",
                    "C": "Contemporary neuroscience research",
                    "D": "Rehabilitation medicine practices"
                },
                "correct": "B"
            },
            "C2": {
                "passage": "The epistemological foundations of scientific inquiry rest upon the intricate interplay between empirical observation and theoretical frameworks. Paradigmatic shifts in scientific understanding often emerge when accumulated anomalies challenge existing theoretical constructs, necessitating fundamental reconceptualization of underlying assumptions. This dialectical process embodies the self-correcting nature of scientific methodology.",
                "question": "When do paradigmatic shifts in scientific understanding typically occur?",
                "options": {
                    "A": "When empirical observation begins",
                    "B": "When accumulated anomalies challenge existing theoretical constructs",
                    "C": "When theoretical frameworks are first established",
                    "D": "When scientific methodology is questioned"
                },
                "correct": "B"
            }
        }
        
        passage_data = reading_passages.get(level, reading_passages["B1"])
        
        return {
            "question_id": f"reading_{level}_{random.randint(1000, 9999)}",
            "skill": "reading",
            "level": level,
            "passage": passage_data["passage"],
            "question": passage_data["question"],
            "options": passage_data["options"],
            "correct_answer": passage_data["correct"],
            "explanation": "The answer can be found in the passage.",
            "passage_length": len(passage_data["passage"].split()),
            "source": "curated_passages"
        }
    
    async def _create_listening_question(self, level: str) -> Dict:
        """듣기 문제 생성 (시나리오 기반)"""
        
        listening_scenarios = {
            "A1": {
                "scenario": "You hear someone say: 'Hello, my name is Sarah. I am from Canada. Nice to meet you.'",
                "question": "Where is Sarah from?",
                "options": {"A": "Canada", "B": "America", "C": "England", "D": "Australia"},
                "correct": "A"
            },
            "A2": {
                "scenario": "You hear an announcement: 'The train to Manchester will depart from platform 3 at 2:30 PM. Please have your tickets ready.'",
                "question": "What time does the train leave?",
                "options": {"A": "2:00 PM", "B": "2:30 PM", "C": "3:00 PM", "D": "3:30 PM"},
                "correct": "B"
            },
            "B1": {
                "scenario": "You hear a weather forecast: 'Tomorrow will be partly cloudy with temperatures reaching 18 degrees Celsius. There's a 30% chance of light rain in the afternoon.'",
                "question": "What is the chance of rain tomorrow afternoon?",
                "options": {"A": "18%", "B": "30%", "C": "50%", "D": "70%"},
                "correct": "B"
            },
            "B2": {
                "scenario": "You hear a news report: 'The company's quarterly earnings exceeded expectations by 15%, resulting in a significant boost to investor confidence and a 3% increase in stock prices.'",
                "question": "How much did the company exceed earnings expectations?",
                "options": {"A": "3%", "B": "15%", "C": "30%", "D": "45%"},
                "correct": "B"
            }
        }
        
        scenario = listening_scenarios.get(level, listening_scenarios["A2"])
        
        return {
            "question_id": f"listening_{level}_{random.randint(1000, 9999)}",
            "skill": "listening",
            "level": level,
            "audio_scenario": scenario["scenario"],
            "question": scenario["question"],
            "options": scenario["options"],
            "correct_answer": scenario["correct"],
            "explanation": "Based on the audio information provided.",
            "source": "listening_scenarios"
        }


class LevelTestService:
    """API 기반 개선된 레벨 테스트 서비스"""
    
    def __init__(self):
        """초기화"""
        
        # OpenAI 설정
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.openai_client = OpenAI(api_key=self.openai_api_key) if self.openai_api_key else None
        
        # 외부 API 서비스
        self.quick_api = QuickStartLanguageAPI()
        
        # 세션 관리
        self.active_sessions = {}
        
        # CEFR 레벨 정의
        self.cefr_levels = {
            "A1": {"name": "Beginner", "points": 1, "description": "Basic everyday expressions"},
            "A2": {"name": "Elementary", "points": 2, "description": "Simple communication"},
            "B1": {"name": "Intermediate", "points": 3, "description": "Clear standard input"},
            "B2": {"name": "Upper-Intermediate", "points": 4, "description": "Complex text understanding"},
            "C1": {"name": "Advanced", "points": 5, "description": "Fluent and spontaneous"},
            "C2": {"name": "Proficient", "points": 6, "description": "Near-native fluency"}
        }
        
        # 초기화 플래그
        self._initialization_started = False
    
    async def _ensure_initialized(self):
        """데이터셋 초기화 보장"""
        if not self._initialization_started:
            self._initialization_started = True
            try:
                await self.quick_api.initialize_datasets()
            except Exception as e:
                logger.error(f"데이터셋 초기화 오류: {e}")
    
    async def start_level_test(self, user_id: str, language: str = "english") -> Dict:
        """레벨 테스트 시작 - 5개 언어 지원"""
        
        try:
            await self._ensure_initialized()
            
            # 언어 매핑 및 검증
            language_map = {
                "korean": "ko",
                "english": "en", 
                "japanese": "ja",
                "chinese": "zh",
                "french": "fr"
            }
            
            language_code = language_map.get(language.lower(), "en")
            
            # 지원하지 않는 언어 체크
            if language_code not in ["ko", "en", "ja", "zh", "fr"]:
                return {
                    "success": False,
                    "error": f"지원하지 않는 언어: {language}. 지원 언어: ko, en, ja, zh, fr"
                }
            
            session_id = f"level_test_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # 세션 초기화
            session_data = {
                "session_id": session_id,
                "user_id": user_id,
                "language": language_code,  # 언어 코드 저장
                "start_time": datetime.now().isoformat(),
                "current_question": 0,
                "total_questions": 15,
                "estimated_level": "A2",
                "confidence": 0.1,
                "responses": [],
                "skill_scores": {"vocabulary": [], "grammar": [], "reading": [], "listening": []},
                "completed": False,
                "question_sources": []
            }
            
            self.active_sessions[session_id] = session_data
            
            # 첫 번째 문제 생성 (언어별)
            first_question = await self._generate_question_multilang(
                session_data, "vocabulary", "A2", language_code
            )
            
            language_names = {
                "ko": "한국어",
                "en": "English", 
                "ja": "日本語",
                "zh": "中文",
                "fr": "Français"
            }
            
            logger.info(f"레벨 테스트 시작: {session_id} ({language_names.get(language_code)})")
            
            return {
                "success": True,
                "session_id": session_id,
                "language": language_code,
                "language_name": language_names.get(language_code),
                "estimated_duration": "10-15 minutes",
                "total_questions": "10-15 (adaptive)",
                "current_question": first_question,
                "data_sources": ["multilingual_vocabulary", "grammar_templates", "reading_passages"],
                "progress": {
                    "completed": 0,
                    "total": session_data["total_questions"],
                    "estimated_level": "Unknown"
                }
            }
            
        except Exception as e:
            logger.error(f"다국어 레벨 테스트 시작 오류: {e}")
            return {
                "success": False,
                "error": f"레벨 테스트를 시작할 수 없습니다: {str(e)}"
            }
    
    async def _generate_question(self, session: Dict, skill: str, level: str) -> Dict:
        """문제 생성 (다중 소스) - 다국어 지원 추가"""
        
        # 세션에서 언어 코드 추출
        language = session.get("language", "en")
        
        # 영어가 아닌 경우, 다국어 문제 생성 우선 시도
        if language != "en":
            try:
                logger.debug(f"다국어 문제 생성 시도: {language}")
                question = await self._generate_question_multilang(session, skill, level, language)
                
                if question and question.get("question"):
                    session["question_sources"].append("multilingual")
                    logger.debug(f"다국어 문제 생성 성공: {language}")
                    return question
                else:
                    logger.warning(f"다국어 문제 생성 실패, 영어로 대체: {language}")
                    
            except Exception as e:
                logger.warning(f"다국어 문제 생성 오류, 영어로 대체 ({language}): {e}")
        
        # 영어 문제 또는 다국어 실패 시 기존 로직 실행
        try:
            # 1. 우선 API 기반 검증된 문제 생성 시도 (영어)
            api_questions = await self.quick_api.generate_verified_questions(level, skill, 1)
            
            if api_questions:
                question = api_questions[0]
                question["source"] = "verified_api"
                question["language"] = "en"  # 언어 정보 추가
                session["question_sources"].append("verified_api")
                return question
            
            # 2. OpenAI 백업 (영어)
            elif self.openai_client:
                question = await self._generate_openai_question(session, skill, level)
                question["source"] = "openai_backup"
                question["language"] = "en"  # 언어 정보 추가
                session["question_sources"].append("openai_backup")
                return question
            
            # 3. 대체 문제 (언어별)
            else:
                if language != "en":
                    # 다국어 대체 문제
                    question = self._get_fallback_question_multilang(skill, level, language, session["current_question"] + 1)
                else:
                    # 영어 대체 문제
                    question = self._get_fallback_question(skill, level, session["current_question"] + 1)
                    question["language"] = "en"
                
                question["source"] = "fallback"
                session["question_sources"].append("fallback")
                return question
                
        except Exception as e:
            logger.error(f"문제 생성 오류: {e}")
            
            # 최종 대체 (언어별)
            if language != "en":
                question = self._get_fallback_question_multilang(skill, level, language, session["current_question"] + 1)
            else:
                question = self._get_fallback_question(skill, level, session["current_question"] + 1)
                question["language"] = "en"
            
            question["source"] = "fallback"
            session["question_sources"].append("fallback")
            return question
        
    async def _generate_question_multilang(
        self, 
        session: Dict, 
        skill: str, 
        level: str, 
        language: str
    ) -> Dict:
        """언어별 문제 생성"""
        
        try:
            question_id = f"q_{language}_{session['session_id']}_{session['current_question']}"
            
            if skill == "vocabulary":
                return self._create_vocab_question_multilang(level, language, question_id)
            elif skill == "grammar":
                return self._create_grammar_question_multilang(level, language, question_id)
            elif skill == "reading":
                return self._create_reading_question_multilang(level, language, question_id)
            else:
                return self._create_listening_question_multilang(level, language, question_id)
                
        except Exception as e:
            logger.error(f"다국어 문제 생성 오류: {e}")
            return self._get_fallback_question_multilang(skill, level, language, session["current_question"] + 1)
    
    def _create_vocab_question_multilang(self, level: str, language: str, question_id: str) -> Dict:
        """언어별 어휘 문제 생성"""
        
        vocab_list = BASIC_VOCABULARY.get(language, BASIC_VOCABULARY["en"])
        
        if level == "A1":
            word_index = 0  # 첫 번째 기본 단어
        elif level == "A2":
            word_index = min(3, len(vocab_list) - 1)
        else:
            word_index = min(6, len(vocab_list) - 1)
        
        word = vocab_list[word_index]
        
        # 언어별 문제 형식
        question_formats = {
            "ko": f"'{word}'의 의미는 무엇입니까?",
            "en": f"What does '{word}' mean?",
            "ja": f"'{word}'の意味は何ですか？",
            "zh": f"'{word}'是什么意思？",
            "fr": f"Que signifie '{word}' ?"
        }
        
        # 언어별 선택지 (기본적인 의미)
        meaning_options = {
            "ko": {
                "안녕하세요": {"A": "인사말", "B": "작별 인사", "C": "감사 인사", "D": "사과"},
                "감사합니다": {"A": "인사말", "B": "감사 표현", "C": "사과", "D": "질문"},
                "죄송합니다": {"A": "사과", "B": "인사말", "C": "감사", "D": "질문"},
                "도와주세요": {"A": "도움 요청", "B": "인사말", "C": "감사", "D": "작별"}
            },
            "en": {
                "hello": {"A": "greeting", "B": "goodbye", "C": "thanks", "D": "sorry"},
                "thank you": {"A": "greeting", "B": "expression of gratitude", "C": "apology", "D": "question"},
                "sorry": {"A": "apology", "B": "greeting", "C": "thanks", "D": "question"},
                "help": {"A": "assistance", "B": "greeting", "C": "goodbye", "D": "thanks"}
            },
            "ja": {
                "こんにちは": {"A": "挨拶", "B": "さようなら", "C": "感謝", "D": "謝罪"},
                "ありがとうございます": {"A": "挨拶", "B": "感謝の表現", "C": "謝罪", "D": "質問"},
                "すみません": {"A": "謝罪", "B": "挨拶", "C": "感謝", "D": "質問"},
                "手伝って": {"A": "助けを求める", "B": "挨拶", "C": "感謝", "D": "さようなら"}
            },
            "zh": {
                "你好": {"A": "问候", "B": "再见", "C": "谢谢", "D": "对不起"},
                "谢谢": {"A": "问候", "B": "感谢表达", "C": "道歉", "D": "问题"},
                "对不起": {"A": "道歉", "B": "问候", "C": "谢谢", "D": "问题"},
                "帮助": {"A": "援助", "B": "问候", "C": "再见", "D": "谢谢"}
            },
            "fr": {
                "bonjour": {"A": "salutation", "B": "au revoir", "C": "merci", "D": "pardon"},
                "merci": {"A": "salutation", "B": "expression de gratitude", "C": "excuse", "D": "question"},
                "désolé": {"A": "excuse", "B": "salutation", "C": "merci", "D": "question"},
                "aide": {"A": "assistance", "B": "salutation", "C": "au revoir", "D": "merci"}
            }
        }
        
        options = meaning_options.get(language, {}).get(word, {"A": "option1", "B": "option2", "C": "option3", "D": "option4"})
        
        return {
            "question_id": question_id,
            "skill": "vocabulary",
            "level": level,
            "language": language,
            "question": question_formats.get(language, question_formats["en"]),
            "options": options,
            "correct_answer": "A",  # 첫 번째가 항상 정답
            "explanation": f"'{word}' 의미 설명",
            "word": word,
            "source": "multilingual_vocabulary"
        }
    
    def _create_grammar_question_multilang(self, level: str, language: str, question_id: str) -> Dict:
        """언어별 문법 문제 생성"""
        
        templates = GRAMMAR_TEMPLATES.get(language, GRAMMAR_TEMPLATES["en"])
        template = templates.get(level, templates.get("A1", {}))
        
        if not template:
            return self._get_fallback_question_multilang("grammar", level, language, 1)
        
        return {
            "question_id": question_id,
            "skill": "grammar",
            "level": level,
            "language": language,
            "question": template["template"],
            "options": template["options"],
            "correct_answer": template["correct"],
            "explanation": f"문법 포인트: {template['point']}",
            "grammar_point": template["point"],
            "source": "grammar_templates"
        }
    
    def _create_reading_question_multilang(self, level: str, language: str, question_id: str) -> Dict:
        """언어별 독해 문제 생성"""
        
        passages = READING_PASSAGES.get(language, READING_PASSAGES["en"])
        passage_data = passages.get(level, passages.get("A1", {}))
        
        if not passage_data:
            return self._get_fallback_question_multilang("reading", level, language, 1)
        
        return {
            "question_id": question_id,
            "skill": "reading",
            "level": level,
            "language": language,
            "passage": passage_data["passage"],
            "question": passage_data["question"],
            "options": passage_data["options"],
            "correct_answer": passage_data["correct"],
            "explanation": "지문에서 답을 찾을 수 있습니다.",
            "passage_length": len(passage_data["passage"].split()),
            "source": "reading_passages"
        }
    
    def _create_listening_question_multilang(self, level: str, language: str, question_id: str) -> Dict:
        """언어별 듣기 문제 생성"""
        
        listening_scenarios = {
            "ko": {
                "A1": {
                    "scenario": "누군가 말합니다: '안녕하세요, 저는 김민수입니다. 한국에서 왔어요. 만나서 반가워요.'",
                    "question": "김민수는 어느 나라에서 왔어요?",
                    "options": {"A": "한국", "B": "일본", "C": "중국", "D": "미국"},
                    "correct": "A"
                },
                "A2": {
                    "scenario": "안내방송을 듣습니다: '부산행 KTX는 3번 승강장에서 오후 2시 30분에 출발합니다. 승차권을 준비해주세요.'",
                    "question": "부산행 KTX는 몇 시에 출발합니까?",
                    "options": {"A": "오후 2시", "B": "오후 2시 30분", "C": "오후 3시", "D": "오후 3시 30분"},
                    "correct": "B"
                }
            },
            "en": {
                "A1": {
                    "scenario": "You hear someone say: 'Hello, my name is Sarah. I am from Canada. Nice to meet you.'",
                    "question": "Where is Sarah from?",
                    "options": {"A": "Canada", "B": "America", "C": "England", "D": "Australia"},
                    "correct": "A"
                },
                "A2": {
                    "scenario": "You hear an announcement: 'The train to Manchester will depart from platform 3 at 2:30 PM. Please have your tickets ready.'",
                    "question": "What time does the train leave?",
                    "options": {"A": "2:00 PM", "B": "2:30 PM", "C": "3:00 PM", "D": "3:30 PM"},
                    "correct": "B"
                }
            },
            "ja": {
                "A1": {
                    "scenario": "誰かが言います：「こんにちは、私は田中です。日本から来ました。よろしくお願いします。」",
                    "question": "田中さんはどこから来ましたか？",
                    "options": {"A": "日本", "B": "韓国", "C": "中国", "D": "アメリカ"},
                    "correct": "A"
                }
            },
            "zh": {
                "A1": {
                    "scenario": "你听到有人说：'你好，我叫李明。我来自中国。很高兴认识你。'",
                    "question": "李明来自哪里？",
                    "options": {"A": "中国", "B": "日本", "C": "韩国", "D": "美国"},
                    "correct": "A"
                }
            },
            "fr": {
                "A1": {
                    "scenario": "Vous entendez quelqu'un dire : 'Bonjour, je m'appelle Marie. Je viens de France. Enchanté de vous rencontrer.'",
                    "question": "D'où vient Marie ?",
                    "options": {"A": "France", "B": "Canada", "C": "Belgique", "D": "Suisse"},
                    "correct": "A"
                }
            }
        }
        
        scenario = listening_scenarios.get(language, listening_scenarios["en"]).get(level, 
                   listening_scenarios.get(language, listening_scenarios["en"]).get("A1", {}))
        
        if not scenario:
            return self._get_fallback_question_multilang("listening", level, language, 1)
        
        return {
            "question_id": question_id,
            "skill": "listening",
            "level": level,
            "language": language,
            "audio_scenario": scenario["scenario"],
            "question": scenario["question"],
            "options": scenario["options"],
            "correct_answer": scenario["correct"],
            "explanation": "오디오 정보를 바탕으로 답했습니다.",
            "source": "listening_scenarios"
        }
    
    def _get_fallback_question_multilang(self, skill: str, level: str, language: str, question_number: int) -> Dict:
        """언어별 대체 문제"""
        
        fallback_questions = {
            "ko": "이것은 샘플 문제입니다.",
            "en": "This is a sample question.",
            "ja": "これはサンプル問題です。",
            "zh": "这是一个示例问题。",
            "fr": "Ceci est une question d'exemple."
        }
        
        fallback_options = {
            "ko": {"A": "옵션 A", "B": "옵션 B", "C": "옵션 C", "D": "옵션 D"},
            "en": {"A": "Option A", "B": "Option B", "C": "Option C", "D": "Option D"},
            "ja": {"A": "選択肢A", "B": "選択肢B", "C": "選択肢C", "D": "選択肢D"},
            "zh": {"A": "选项A", "B": "选项B", "C": "选项C", "D": "选项D"},
            "fr": {"A": "Option A", "B": "Option B", "C": "Option C", "D": "Option D"}
        }
        
        question_text = fallback_questions.get(language, fallback_questions["en"])
        options = fallback_options.get(language, fallback_options["en"])
        
        return {
            "question_id": f"fallback_{language}_{skill}_{level}_{question_number}",
            "skill": skill,
            "level": level,
            "language": language,
            "question": question_text,
            "options": options,
            "correct_answer": "A",
            "explanation": "대체 문제입니다.",
            "source": "fallback"
        }
    
    async def _generate_openai_question(self, session: Dict, skill: str, level: str) -> Dict:
        """OpenAI 기반 문제 생성"""
        
        question_id = f"q_{session['session_id']}_{session['current_question']}"
        
        prompt = f"""
        Create a {level} level {skill} question for English language assessment.
        
        Requirements:
        - Exactly {level} difficulty (CEFR standard)
        - Test {skill} skills specifically
        - Multiple choice with 4 options (A, B, C, D)
        - Clear, unambiguous correct answer
        
        Return ONLY valid JSON:
        {{
            "question": "...",
            "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
            "correct_answer": "B",
            "explanation": "..."
        }}
        """
        
        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert language assessment creator."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=800
            )
            
            question_data = json.loads(response.choices[0].message.content)
            question_data.update({
                "question_id": question_id,
                "skill": skill,
                "level": level,
                "session_id": session["session_id"],
                "question_number": session["current_question"] + 1
            })
            
            return question_data
            
        except Exception as e:
            logger.error(f"OpenAI 문제 생성 오류: {e}")
            return self._get_fallback_question(skill, level, session["current_question"] + 1)
    
    def _get_fallback_question(self, skill: str, level: str, question_number: int) -> Dict:
        """대체 문제"""
        
        fallback_questions = {
            "vocabulary": {
                "A1": {
                    "question": "What do you call the meal you eat in the morning?",
                    "options": {"A": "breakfast", "B": "lunch", "C": "dinner", "D": "snack"},
                    "correct_answer": "A",
                    "explanation": "Breakfast is the first meal of the day."
                },
                "A2": {
                    "question": "Choose the correct word: 'I'm _____ about the test results.'",
                    "options": {"A": "worried", "B": "worry", "C": "worrying", "D": "worries"},
                    "correct_answer": "A",
                    "explanation": "We use adjectives ending in -ed to describe feelings."
                },
                "B1": {
                    "question": "The company decided to _____ its business to other countries.",
                    "options": {"A": "expand", "B": "expensive", "C": "explain", "D": "explore"},
                    "correct_answer": "A",
                    "explanation": "Expand means to make something bigger or reach more places."
                }
            },
            "grammar": {
                "A1": {
                    "question": "_____ name is John.",
                    "options": {"A": "His", "B": "He", "C": "Him", "D": "He's"},
                    "correct_answer": "A",
                    "explanation": "We use possessive adjectives before nouns."
                },
                "A2": {
                    "question": "Yesterday I _____ to the cinema.",
                    "options": {"A": "go", "B": "went", "C": "going", "D": "will go"},
                    "correct_answer": "B",
                    "explanation": "We use past simple for completed actions in the past."
                }
            }
        }
        
        skill_questions = fallback_questions.get(skill, fallback_questions["vocabulary"])
        question = skill_questions.get(level, skill_questions.get("A2", {
            "question": "This is a sample question.",
            "options": {"A": "Option A", "B": "Option B", "C": "Option C", "D": "Option D"},
            "correct_answer": "A",
            "explanation": "This is a fallback question."
        }))
        
        question.update({
            "question_id": f"fallback_{skill}_{level}_{question_number}",
            "skill": skill,
            "level": level,
            "question_number": question_number
        })
        
        return question
    
    async def submit_answer(self, session_id: str, question_id: str, answer: str) -> Dict:
        """답변 제출 및 처리"""
        
        try:
            if session_id not in self.active_sessions:
                return {
                    "success": False,
                    "error": "유효하지 않은 세션입니다."
                }
            
            session = self.active_sessions[session_id]
            
            if session["completed"]:
                return {
                    "success": False,
                    "error": "이미 완료된 테스트입니다."
                }
            
            # 답변 평가
            evaluation = await self._evaluate_answer(question_id, answer, session)
            session["responses"].append(evaluation)
            session["current_question"] += 1
            
            # 스킬별 점수 업데이트
            skill = evaluation["skill"]
            session["skill_scores"][skill].append(evaluation["score"])
            
            # 레벨 추정 업데이트
            await self._update_level_estimate(session)
            
            # 테스트 완료 조건 확인
            if (session["confidence"] >= 0.85 or 
                session["current_question"] >= session["total_questions"] or
                len(session["responses"]) >= 15):
                
                # 테스트 완료
                final_result = await self._complete_test(session)
                session["completed"] = True
                session["final_result"] = final_result
                
                return {
                    "success": True,
                    "status": "completed",
                    "final_result": final_result
                }
            
            else:
                # 다음 문제 생성
                next_skill = self._determine_next_skill(session)
                next_level = session["estimated_level"]
                next_question = await self._generate_question(session, next_skill, next_level)
                
                return {
                    "success": True,
                    "status": "continue",
                    "next_question": next_question,
                    "progress": {
                        "completed": session["current_question"],
                        "total": session["total_questions"],
                        "estimated_level": session["estimated_level"],
                        "confidence": round(session["confidence"], 2)
                    }
                }
                
        except Exception as e:
            logger.error(f"답변 처리 오류: {e}")
            return {
                "success": False,
                "error": f"답변 처리 중 오류가 발생했습니다: {str(e)}"
            }
    
    async def _evaluate_answer(self, question_id: str, answer: str, session: Dict) -> Dict:
        """답변 평가"""
        try:
            # 간단한 평가 로직
            score = 85 if answer.upper() in ["A", "B", "C", "D"] else 0
            correct = True if score > 0 else False
            
            return {
                "question_id": question_id,
                "user_answer": answer,
                "correct": correct,
                "score": score,
                "skill": self._get_question_skill(question_id, session),
                "level": session["estimated_level"],
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"답변 평가 오류: {e}")
            return {
                "question_id": question_id,
                "user_answer": answer,
                "correct": False,
                "score": 0,
                "skill": "vocabulary",
                "level": session["estimated_level"],
                "timestamp": datetime.now().isoformat()
            }
    
    async def _update_level_estimate(self, session: Dict):
        """레벨 추정 업데이트"""
        try:
            responses = session["responses"]
            if not responses:
                return
            
            # 최근 3-5개 답변의 평균 점수
            recent_scores = [r["score"] for r in responses[-5:]]
            avg_score = sum(recent_scores) / len(recent_scores)
            
            # 점수에 따른 레벨 추정
            if avg_score >= 90:
                target_level = self._get_higher_level(session["estimated_level"])
            elif avg_score <= 40:
                target_level = self._get_lower_level(session["estimated_level"])
            else:
                target_level = session["estimated_level"]
            
            session["estimated_level"] = target_level
            
            # 신뢰도 계산
            consistency = self._calculate_consistency(responses)
            response_count_factor = min(len(responses) / 10, 1.0)
            session["confidence"] = consistency * response_count_factor
            
        except Exception as e:
            logger.error(f"레벨 추정 업데이트 오류: {e}")
    
    def _get_higher_level(self, current_level: str) -> str:
        """다음 레벨 반환"""
        levels = ["A1", "A2", "B1", "B2", "C1", "C2"]
        try:
            current_index = levels.index(current_level)
            return levels[min(current_index + 1, len(levels) - 1)]
        except ValueError:
            return "B1"
    
    def _get_lower_level(self, current_level: str) -> str:
        """이전 레벨 반환"""
        levels = ["A1", "A2", "B1", "B2", "C1", "C2"]
        try:
            current_index = levels.index(current_level)
            return levels[max(current_index - 1, 0)]
        except ValueError:
            return "A2"
    
    def _calculate_consistency(self, responses: List[Dict]) -> float:
        """응답 일관성 계산"""
        if len(responses) < 3:
            return 0.1
        
        scores = [r["score"] for r in responses]
        mean_score = sum(scores) / len(scores)
        variance = sum((score - mean_score) ** 2 for score in scores) / len(scores)
        std_dev = variance ** 0.5
        
        consistency = max(0, 1 - (std_dev / 50))
        return min(consistency, 0.95)
    
    def _determine_next_skill(self, session: Dict) -> str:
        """다음 테스트할 스킬 결정"""
        skill_counts = {skill: len(scores) for skill, scores in session["skill_scores"].items()}
        
        min_count = min(skill_counts.values())
        least_tested_skills = [skill for skill, count in skill_counts.items() if count == min_count]
        
        skills_order = ["vocabulary", "grammar", "reading", "listening"]
        for skill in skills_order:
            if skill in least_tested_skills:
                return skill
        
        return "vocabulary"
    
    def _get_question_skill(self, question_id: str, session: Dict) -> str:
        """문제의 스킬 영역 반환"""
        try:
            if 'vocab' in question_id:
                return "vocabulary"
            elif 'grammar' in question_id:
                return "grammar"
            elif 'reading' in question_id:
                return "reading"
            elif 'listening' in question_id:
                return "listening"
            else:
                # 기본 로직
                question_num = int(question_id.split('_')[-1]) if question_id.split('_')[-1].isdigit() else 0
                skills = ["vocabulary", "grammar", "reading", "listening"]
                return skills[question_num % 4]
        except:
            return "vocabulary"
    
    async def _complete_test(self, session: Dict) -> Dict:
        """테스트 완료 및 최종 결과 생성"""
        try:
            responses = session["responses"]
            
            # 스킬별 평균 점수 계산
            skill_averages = {}
            for skill, scores in session["skill_scores"].items():
                if scores:
                    skill_averages[skill] = sum(scores) / len(scores)
                else:
                    skill_averages[skill] = 0
            
            # 전체 평균 점수
            overall_score = sum(skill_averages.values()) / len(skill_averages)
            
            # 최종 레벨 결정
            final_level = self._score_to_level(overall_score)
            
            # 강약점 분석
            strengths = [skill for skill, score in skill_averages.items() if score >= 75]
            weaknesses = [skill for skill, score in skill_averages.items() if score < 60]
            
            # 학습 추천사항 생성
            recommendations = await self._generate_recommendations(final_level, weaknesses, session["language"])
            
            # 소스 분석
            source_analysis = self._analyze_question_sources(session["question_sources"])
            
            result = {
                "user_id": session["user_id"],
                "session_id": session["session_id"],
                "final_level": final_level,
                "level_description": self.cefr_levels[final_level]["description"],
                "overall_score": round(overall_score, 1),
                "skill_breakdown": {
                    skill: round(score, 1) for skill, score in skill_averages.items()
                },
                "strengths": strengths,
                "areas_to_improve": weaknesses,
                "confidence": round(session["confidence"], 2),
                "questions_answered": len(responses),
                "test_duration": self._calculate_duration(session),
                "question_sources": source_analysis,
                "data_quality": self._assess_data_quality(source_analysis),
                "recommendations": recommendations,
                "next_steps": self._generate_next_steps(final_level),
                "completed_at": datetime.now().isoformat()
            }
            
            logger.info(f"레벨 테스트 완료: {session['session_id']} - 레벨: {final_level}")
            
            return result
            
        except Exception as e:
            logger.error(f"테스트 완료 처리 오류: {e}")
            return {
                "error": "테스트 결과 처리 중 오류가 발생했습니다.",
                "session_id": session["session_id"]
            }
    
    def _score_to_level(self, score: float) -> str:
        """점수를 CEFR 레벨로 변환"""
        if score >= 90:
            return "C2"
        elif score >= 80:
            return "C1"
        elif score >= 70:
            return "B2"
        elif score >= 60:
            return "B1"
        elif score >= 45:
            return "A2"
        else:
            return "A1"
    
    async def _generate_recommendations(self, level: str, weak_areas: List[str], language: str) -> List[str]:
        """개인화된 학습 추천사항 생성"""
        try:
            # 기본 추천사항
            default_recommendations = {
                "A1": [
                    "Focus on learning basic vocabulary (500-1000 most common words)",
                    "Practice simple present tense and basic sentence structures",
                    "Start with greetings and everyday conversations"
                ],
                "A2": [
                    "Expand vocabulary to 1500+ words including past/future topics", 
                    "Practice past and future tenses in real situations",
                    "Read simple stories and watch beginner-friendly videos"
                ],
                "B1": [
                    "Build vocabulary to 2500+ words including abstract concepts",
                    "Master present perfect and conditional sentences",
                    "Practice expressing opinions and giving explanations"
                ],
                "B2": [
                    "Learn advanced vocabulary and idiomatic expressions",
                    "Practice complex grammar structures and formal writing",
                    "Engage with authentic materials like news and academic texts"
                ],
                "C1": [
                    "Focus on nuanced vocabulary and register awareness",
                    "Practice advanced writing and presentation skills",
                    "Engage in complex discussions and debates"
                ],
                "C2": [
                    "Perfect stylistic variety and cultural knowledge",
                    "Practice specialized and professional communication",
                    "Engage with literature and academic research"
                ]
            }
            
            recommendations = default_recommendations.get(level, default_recommendations["B1"])
            
            # 약점 기반 추가 추천
            if weak_areas:
                for weakness in weak_areas[:2]:  # 최대 2개
                    if weakness == "vocabulary":
                        recommendations.append(f"Extra focus needed on {level}-level vocabulary building")
                    elif weakness == "grammar":
                        recommendations.append(f"Practice {level}-level grammar structures daily")
                    elif weakness == "reading":
                        recommendations.append(f"Read {level}-appropriate texts for 15-20 minutes daily")
                    elif weakness == "listening":
                        recommendations.append(f"Listen to {level}-level audio content regularly")
            
            return recommendations[:4]  # 최대 4개
            
        except Exception as e:
            logger.error(f"추천사항 생성 오류: {e}")
            return [
                f"Continue practicing at {level} level",
                "Focus on your weak areas",
                "Practice regularly for best results"
            ]
    
    def _generate_next_steps(self, level: str) -> List[str]:
        """다음 단계 제안"""
        next_steps = {
            "A1": [
                "Build basic vocabulary (500-1000 words)",
                "Practice simple present tense",
                "Learn common greetings and introductions"
            ],
            "A2": [
                "Expand vocabulary to 1500+ words",
                "Practice past and future tenses",
                "Work on simple conversations"
            ],
            "B1": [
                "Build vocabulary to 2500+ words",
                "Practice complex sentence structures",
                "Start reading intermediate texts"
            ],
            "B2": [
                "Master advanced grammar structures",
                "Practice writing and speaking fluently",
                "Read news articles and literature"
            ],
            "C1": [
                "Refine nuanced language use",
                "Practice formal and academic writing",
                "Engage in complex discussions"
            ],
            "C2": [
                "Perfect near-native fluency",
                "Study specialized vocabulary",
                "Practice professional communication"
            ]
        }
        
        return next_steps.get(level, next_steps["B1"])
    
    def _calculate_duration(self, session: Dict) -> str:
        """테스트 소요 시간 계산"""
        try:
            start_time = datetime.fromisoformat(session["start_time"])
            duration = datetime.now() - start_time
            minutes = int(duration.total_seconds() / 60)
            return f"{minutes} minutes"
        except:
            return "Unknown"
    
    def _analyze_question_sources(self, sources: List[str]) -> Dict:
        """문제 출처 분석"""
        
        from collections import Counter
        source_counts = Counter(sources)
        
        return {
            "total_questions": len(sources),
            "verified_api": source_counts.get("verified_api", 0),
            "openai_backup": source_counts.get("openai_backup", 0),
            "fallback": source_counts.get("fallback", 0),
            "quality_score": self._calculate_source_quality(source_counts)
        }
    
    def _calculate_source_quality(self, source_counts) -> float:
        """소스 품질 점수 계산"""
        
        total = sum(source_counts.values())
        if total == 0:
            return 0.0
        
        quality_score = (
            source_counts.get("verified_api", 0) * 1.0 +
            source_counts.get("openai_backup", 0) * 0.7 +
            source_counts.get("fallback", 0) * 0.3
        ) / total
        
        return round(quality_score, 2)
    
    def _assess_data_quality(self, source_analysis: Dict) -> str:
        """데이터 품질 평가"""
        
        quality_score = source_analysis["quality_score"]
        
        if quality_score >= 0.8:
            return "high"
        elif quality_score >= 0.6:
            return "medium"
        else:
            return "low"
    
    def get_session_status(self, session_id: str) -> Dict:
        """세션 상태 조회"""
        if session_id not in self.active_sessions:
            return {"exists": False}
        
        session = self.active_sessions[session_id]
        return {
            "exists": True,
            "completed": session["completed"],
            "progress": {
                "current_question": session["current_question"],
                "total_questions": session["total_questions"],
                "estimated_level": session["estimated_level"],
                "confidence": session["confidence"]
            },
            "started_at": session["start_time"],
            "data_sources_used": len(set(session.get("question_sources", [])))
        }

# 전역 서비스 인스턴스
level_test_service = LevelTestService()