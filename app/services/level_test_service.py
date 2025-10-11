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
import httpx
from datetime import datetime
from typing import Dict, List, Optional

import self
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
        "A1": [
            {"template": "She _____ to school every day.", "options": {"A": "go", "B": "goes", "C": "going", "D": "went"}, "correct": "B", "point": "3인칭 단수 현재"},
            {"template": "I _____ a student.", "options": {"A": "is", "B": "are", "C": "am", "D": "be"}, "correct": "C", "point": "Be동사 (1인칭)"},
            {"template": "There _____ two books on the table.", "options": {"A": "is", "B": "are", "C": "am", "D": "be"}, "correct": "B", "point": "There is/are (복수)"},
            {"template": "He _____ speak English.", "options": {"A": "not", "B": "don't", "C": "doesn't", "D": "isn't"}, "correct": "C", "point": "일반동사 부정문"},
            {"template": "_____ you like coffee?", "options": {"A": "Does", "B": "Is", "C": "Do", "D": "Are"}, "correct": "C", "point": "일반동사 의문문"},
            {"template": "This is _____ apple.", "options": {"A": "a", "B": "an", "C": "the", "D": "any"}, "correct": "B", "point": "관사 (an)"},
            {"template": "The cat is _____ the box.", "options": {"A": "on", "B": "at", "C": "in", "D": "of"}, "correct": "C", "point": "전치사 (in)"},
            {"template": "_____ is your name?", "options": {"A": "What", "B": "Who", "C": "Where", "D": "When"}, "correct": "A", "point": "의문사 (What)"},
            {"template": "I can _____ a bike.", "options": {"A": "ride", "B": "rides", "C": "riding", "D": "rode"}, "correct": "A", "point": "조동사 (can + 동사원형)"},
            {"template": "They _____ happy.", "options": {"A": "is", "B": "am", "C": "are", "D": "be"}, "correct": "C", "point": "Be동사 (복수)"},
        ],
        "A2": [
            {"template": "Yesterday, I _____ a movie.", "options": {"A": "see", "B": "saw", "C": "seen", "D": "will see"}, "correct": "B", "point": "단순 과거 시제"},
            {"template": "This book is _____ than that one.", "options": {"A": "interesting", "B": "more interesting", "C": "most interesting", "D": "interestinger"}, "correct": "B", "point": "비교급"},
            {"template": "I am _____ to the park tomorrow.", "options": {"A": "go", "B": "went", "C": "going", "D": "goes"}, "correct": "C", "point": "현재진행형 (미래 표현)"},
            {"template": "She was _____ when I called her.", "options": {"A": "sleep", "B": "slept", "C": "sleeping", "D": "sleeps"}, "correct": "C", "point": "과거진행형"},
            {"template": "You _____ finish your homework now.", "options": {"A": "must", "B": "can", "C": "may", "D": "will"}, "correct": "A", "point": "조동사 (의무)"},
            {"template": "I have _____ seen that movie before.", "options": {"A": "already", "B": "yet", "C": "still", "D": "ever"}, "correct": "A", "point": "현재완료 (already)"},
            {"template": "There isn't _____ milk in the fridge.", "options": {"A": "some", "B": "any", "C": "no", "D": "a"}, "correct": "B", "point": "some/any (부정문)"},
            {"template": "She is the _____ girl in the class.", "options": {"A": "tall", "B": "taller", "C": "tallest", "D": "more tall"}, "correct": "C", "point": "최상급"},
            {"template": "He asked me _____ I was doing.", "options": {"A": "what", "B": "which", "C": "who", "D": "where"}, "correct": "A", "point": "간접 의문문"},
            {"template": "Let's go _____ a walk.", "options": {"A": "to", "B": "on", "C": "in", "D": "for"}, "correct": "D", "point": "관용 표현 (go for a walk)"},
        ],
        "B1": [
            {"template": "I have _____ been to Paris.", "options": {"A": "ever", "B": "never", "C": "yet", "D": "still"}, "correct": "B", "point": "현재완료 (경험)"},
            {"template": "If it rains, I _____ at home.", "options": {"A": "stay", "B": "would stay", "C": "will stay", "D": "stayed"}, "correct": "C", "point": "가정법 (1st Conditional)"},
            {"template": "The phone, _____ is on the table, is mine.", "options": {"A": "who", "B": "which", "C": "what", "D": "where"}, "correct": "B", "point": "관계대명사 (계속적 용법)"},
            {"template": "She has been _____ English for three years.", "options": {"A": "study", "B": "studied", "C": "studying", "D": "studies"}, "correct": "C", "point": "현재완료진행형"},
            {"template": "This work needs to _____ by tomorrow.", "options": {"A": "do", "B": "be done", "C": "doing", "D": "did"}, "correct": "B", "point": "수동태 (조동사 + to 부정사)"},
            {"template": "I used to _____ in a small town.", "options": {"A": "live", "B": "living", "C": "lived", "D": "lives"}, "correct": "A", "point": "used to + 동사원형"},
            {"template": "She said she _____ tired.", "options": {"A": "is", "B": "was", "C": "has been", "D": "will be"}, "correct": "B", "point": "화법 전환 (시제 일치)"},
            {"template": "He is interested _____ learning new things.", "options": {"A": "in", "B": "on", "C": "at", "D": "for"}, "correct": "A", "point": "전치사 + 동명사"},
            {"template": "_____ all his efforts, he failed the exam.", "options": {"A": "Although", "B": "Despite", "C": "Because", "D": "So"}, "correct": "B", "point": "양보 (Despite + 명사)"},
            {"template": "I look forward to _____ you soon.", "options": {"A": "see", "B": "seeing", "C": "saw", "D": "have seen"}, "correct": "B", "point": "to 부정사 vs 전치사 to"},
        ],
        "B2": [
            {"template": "If I _____ you, I would study harder.", "options": {"A": "am", "B": "was", "C": "were", "D": "be"}, "correct": "C", "point": "가정법 과거 (2nd Conditional)"},
            {"template": "By the time you arrive, I _____ dinner.", "options": {"A": "will cook", "B": "am cooking", "C": "will have cooked", "D": "cooked"}, "correct": "C", "point": "미래완료 시제"},
            {"template": "He denied _____ the money.", "options": {"A": "to steal", "B": "stealing", "C": "stole", "D": "steal"}, "correct": "B", "point": "동명사를 목적어로 취하는 동사"},
            {"template": "She insisted that he _____ a doctor.", "options": {"A": "see", "B": "sees", "C": "saw", "D": "is seeing"}, "correct": "A", "point": "가정법 현재 (Subjunctive)"},
            {"template": "The report, _____ conclusions are surprising, was published today.", "options": {"A": "which", "B": "that", "C": "whose", "D": "who"}, "correct": "C", "point": "소유격 관계대명사"},
            {"template": "Having _____ the book, he returned it to the library.", "options": {"A": "read", "B": "reading", "C": "reads", "D": "to read"}, "correct": "A", "point": "분사구문 (완료형)"},
            {"template": "I wish I _____ more time to travel.", "options": {"A": "have", "B": "had", "C": "will have", "D": "am having"}, "correct": "B", "point": "I wish + 가정법 과거"},
            {"template": "It's no use _____ about the past.", "options": {"A": "worry", "B": "to worry", "C": "worrying", "D": "worried"}, "correct": "C", "point": "관용표현 (It's no use -ing)"},
            {"template": "He must _____ very tired after the long journey.", "options": {"A": "be", "B": "have been", "C": "being", "D": "was"}, "correct": "A", "point": "추측의 조동사 (must)"},
            {"template": "_____ hard he tries, he can't seem to win.", "options": {"A": "Whatever", "B": "However", "C": "Whenever", "D": "Wherever"}, "correct": "B", "point": "복합관계부사 (However)"},
        ],
        "C1": [
            {"template": "Not only _____ beautiful, but she is also very intelligent.", "options": {"A": "she is", "B": "is she", "C": "she was", "D": "was she"}, "correct": "B", "point": "도치 (Inversion)"},
            {"template": "If I had known you were coming, I _____ a cake.", "options": {"A": "would bake", "B": "will bake", "C": "would have baked", "D": "baked"}, "correct": "C", "point": "가정법 과거완료 (3rd Conditional)"},
            {"template": "_____ the bad weather, the flight was cancelled.", "options": {"A": "Despite", "B": "Although", "C": "Owing to", "D": "In spite"}, "correct": "C", "point": "전치사 (이유)"},
            {"template": "He is believed _____ a great fortune.", "options": {"A": "to have made", "B": "making", "C": "that he has", "D": "made"}, "correct": "A", "point": "수동태 (to 부정사 완료형)"},
            {"template": "It was the book _____ I found most interesting.", "options": {"A": "what", "B": "that", "C": "who", "D": "where"}, "correct": "B", "point": "강조 구문 (Cleft Sentence)"},
            {"template": "Little _____ that the meeting had been postponed.", "options": {"A": "he knew", "B": "he knows", "C": "did he know", "D": "he has known"}, "correct": "C", "point": "부정어 도치"},
            {"template": "I would rather you _____ that to her.", "options": {"A": "not say", "B": "didn't say", "C": "don't say", "D": "won't say"}, "correct": "B", "point": "would rather + 가정법"},
            {"template": "The company is on the verge of _____ bankrupt.", "options": {"A": "go", "B": "to go", "C": "going", "D": "gone"}, "correct": "C", "point": "관용 표현 (on the verge of -ing)"},
            {"template": "All things _____, it was a successful event.", "options": {"A": "considering", "B": "consider", "C": "considered", "D": "to consider"}, "correct": "C", "point": "독립 분사구문"},
            {"template": "She can't help _____ when she watches that movie.", "options": {"A": "cry", "B": "to cry", "C": "crying", "D": "cried"}, "correct": "C", "point": "관용 표현 (can't help -ing)"},
        ],
        "C2": [
            {"template": "No sooner _____ I sat down than the phone rang.", "options": {"A": "had", "B": "have", "C": "did", "D": "do"}, "correct": "A", "point": "도치 (No sooner...than)"},
            {"template": "If he had taken my advice, he _____ in trouble now.", "options": {"A": "wouldn't have been", "B": "wouldn't be", "C": "won't be", "D": "isn't"}, "correct": "B", "point": "혼합 가정법 (Mixed Conditional)"},
            {"template": "She talks as if she _____ everything.", "options": {"A": "knows", "B": "knew", "C": "has known", "D": "had known"}, "correct": "B", "point": "as if + 가정법"},
            {"template": "The committee recommends that the proposal _____ accepted.", "options": {"A": "is", "B": "will be", "C": "be", "D": "was"}, "correct": "C", "point": "가정법 현재 (Subjunctive)"},
            {"template": "_____ seen as a quiet person, she was actually very outgoing.", "options": {"A": "Albeit", "B": "Despite", "C": "Whereas", "D": "Though"}, "correct": "D", "point": "분사 구문 (접속사 + 과거분사)"},
            {"template": "Come what _____, we will finish this project on time.", "options": {"A": "can", "B": "will", "C": "may", "D": "should"}, "correct": "C", "point": "관용 표현 (Come what may)"},
            {"template": "The problem is _____ to be solved easily.", "options": {"A": "unlikely", "B": "not likely", "C": "alike", "D": "dislike"}, "correct": "A", "point": "형용사 용법 (be unlikely to)"},
            {"template": "So beautifully _____ that the audience gave her a standing ovation.", "options": {"A": "she sang", "B": "sang she", "C": "did she sing", "D": "she did sing"}, "correct": "C", "point": "도치 (So + 부사)"},
            {"template": "The building is said _____ in the 19th century.", "options": {"A": "to be built", "B": "to have been built", "C": "building", "D": "was built"}, "correct": "B", "point": "완료 부정사 수동태"},
            {"template": "Far _____ it for me to criticize, but I think you're making a mistake.", "options": {"A": "be", "B": "is", "C": "was", "D": "are"}, "correct": "A", "point": "관용 표현 (Far be it from me to)"},
        ],
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
        "A1": [
            {"passage": "My name is John. I have a pet dog. His name is Max. Max is big and brown. He likes to play in the park. We play together every day.", "question": "What is the name of John's pet?", "options": {"A": "John", "B": "Max", "C": "Park", "D": "Dog"}, "correct": "B"},
            {"passage": "This is my room. There is a bed and a desk. The bed is small. The desk is big. I read books at my desk. I sleep in my bed.", "question": "What does he do at the desk?", "options": {"A": "Sleep", "B": "Play", "C": "Read books", "D": "Eat"}, "correct": "C"},
            {"passage": "I live in a city. My city is very big. There are many tall buildings and cars. I like my city because it is always busy.", "question": "Why does he like his city?", "options": {"A": "It is quiet", "B": "It is small", "C": "It is always busy", "D": "It has no cars"}, "correct": "C"},
            {"passage": "I eat breakfast every morning at 7 AM. I usually have toast and milk. Toast is a type of bread. It is very delicious.", "question": "What does he usually have for breakfast?", "options": {"A": "Rice and soup", "B": "Only milk", "C": "Toast and milk", "D": "Nothing"}, "correct": "C"},
            {"passage": "My favorite color is blue. The sky is blue. The ocean is also blue. I have a blue shirt and a blue bag. I like blue because it is a calm color.", "question": "What color is the sky?", "options": {"A": "Red", "B": "Green", "C": "Blue", "D": "Yellow"}, "correct": "C"},
        ],
        "A2": [
            {"passage": "Yesterday, Maria went to a restaurant with her friends. She ordered pizza and a salad. Her friends ordered pasta. They talked and laughed a lot. The food was delicious. Maria had a great time.", "question": "What did Maria eat?", "options": {"A": "Pasta", "B": "Only salad", "C": "Pizza and salad", "D": "Pizza and pasta"}, "correct": "C"},
            {"passage": "I am planning a trip to London next month. I will visit the British Museum and see Big Ben. I need to book my flight and hotel soon. I am very excited about this trip.", "question": "What does he need to do soon?", "options": {"A": "Visit the museum", "B": "See Big Ben", "C": "Book his flight and hotel", "D": "Go on the trip"}, "correct": "C"},
            {"passage": "Tom's hobby is painting. He paints pictures of landscapes and people. He uses different colors like blue, green, and red. He has a small studio in his house where he paints every weekend. He wants to have his own exhibition one day.", "question": "When does Tom paint?", "options": {"A": "Every day", "B": "On weekdays", "C": "Every weekend", "D": "Once a month"}, "correct": "C"},
            {"passage": "The local library is a great place to study. It is very quiet and has a lot of books. You can borrow up to five books at a time. The library is open from 9 AM to 6 PM from Monday to Friday.", "question": "How many books can you borrow at once?", "options": {"A": "One", "B": "Three", "C": "Five", "D": "Ten"}, "correct": "C"},
            {"passage": "Sarah works as a nurse in a hospital. She takes care of sick people. Her job is very hard, but she finds it rewarding. She has to work long hours, sometimes even at night. She is proud of her job because she can help people.", "question": "Why is Sarah proud of her job?", "options": {"A": "Because it is easy", "B": "Because she earns a lot of money", "C": "Because she can help people", "D": "Because she works at night"}, "correct": "C"},
        ],
        "B1": [
            {"passage": "Many people are choosing to work from home these days. This has advantages, such as saving time and money on commuting. However, there are also disadvantages, like feeling isolated from colleagues. Companies need to find a balance that works for everyone.", "question": "What is a disadvantage of working from home mentioned in the text?", "options": {"A": "Saving money", "B": "Feeling lonely", "C": "Saving time", "D": "Finding a balance"}, "correct": "B"},
            {"passage": "Regular exercise is essential for good health. It helps to control weight, combat diseases, and improve mood. Experts recommend at least 30 minutes of moderate activity most days of the week. This could include brisk walking, swimming, or cycling.", "question": "What is the minimum recommended daily exercise?", "options": {"A": "30 minutes of intense activity", "B": "1 hour of light activity", "C": "30 minutes of moderate activity", "D": "15 minutes of brisk walking"}, "correct": "C"},
            {"passage": "The internet has changed our lives in many ways. We can now get information instantly, communicate with people around the world, and shop online. However, it is important to be careful about privacy and security when using the internet.", "question": "What should people be careful about when using the internet?", "options": {"A": "Shopping online", "B": "Getting information", "C": "Communicating with people", "D": "Privacy and security"}, "correct": "D"},
            {"passage": "Learning a new language can be a challenging but rewarding experience. It opens up new cultures and ways of thinking. To be successful, it is important to be consistent with your studies and practice speaking as much as possible, even if you make mistakes.", "question": "What is important to be successful in language learning?", "options": {"A": "To avoid making mistakes", "B": "To study only grammar", "C": "To be consistent and practice speaking", "D": "To travel to the country"}, "correct": "C"},
            {"passage": "Public transportation is a good way to reduce traffic and pollution in big cities. Systems like buses, subways, and trains can move a large number of people efficiently. If more people used public transport, our cities would be cleaner and less congested.", "question": "What is a benefit of public transportation?", "options": {"A": "It is faster than a car", "B": "It is more expensive", "C": "It helps reduce traffic and pollution", "D": "It is available everywhere"}, "correct": "C"},
        ],
        "B2": [
            {"passage": "The rise of social media has fundamentally changed how we communicate and consume information. While it allows for unprecedented connectivity, it also poses challenges, including the spread of misinformation and its impact on mental health. It is crucial for users to develop critical thinking skills to navigate this digital landscape.", "question": "What is a major challenge of social media mentioned in the passage?", "options": {"A": "Its high cost", "B": "The spread of false information", "C": "Its lack of connectivity", "D": "Its difficulty of use"}, "correct": "B"},
            {"passage": "Artificial intelligence (AI) is rapidly evolving. From self-driving cars to medical diagnosis, AI is transforming various industries. However, this progress raises ethical questions about job displacement and data privacy that society must address.", "question": "What is one ethical question raised by AI progress?", "options": {"A": "How to make AI more intelligent", "B": "The cost of AI development", "C": "The potential loss of jobs", "D": "Which industry AI will transform next"}, "correct": "C"},
            {"passage": "Globalization has led to a more interconnected world, with goods, capital, and ideas flowing freely across borders. This has spurred economic growth but has also been criticized for increasing inequality and eroding local cultures. The debate over the pros and cons of globalization continues to be a central theme in international politics.", "question": "What is one criticism of globalization?", "options": {"A": "It has slowed economic growth.", "B": "It prevents the flow of ideas.", "C": "It may increase inequality.", "D": "It strengthens local cultures."}, "correct": "C"},
            {"passage": "Urbanization is the process of people moving from rural areas to cities. This trend has been ongoing for centuries but has accelerated in recent decades. While cities offer more opportunities for employment and education, they also face problems such as overcrowding, pollution, and high living costs.", "question": "What is one problem faced by cities due to urbanization?", "options": {"A": "Lack of education", "B": "Too few people", "C": "Low living costs", "D": "Overcrowding and pollution"}, "correct": "D"},
            {"passage": "A healthy diet is crucial for maintaining physical and mental well-being. A balanced diet includes a variety of foods such as fruits, vegetables, whole grains, and lean proteins. It's not about strict limitations, but rather about feeling great, having more energy, and improving your health.", "question": "What does a balanced diet include?", "options": {"A": "Only fruits and vegetables", "B": "Strict and limiting food choices", "C": "A variety of healthy foods", "D": "Mainly lean proteins"}, "correct": "C"},
        ],
        "C1": [
            {"passage": "The concept of a 'circular economy' aims to eliminate waste and promote the continual use of resources. Unlike the traditional linear model of 'take, make, dispose,' a circular system involves designing products for durability, reuse, and recyclability. This approach is seen by many as a key strategy for achieving sustainable development.", "question": "What is the primary goal of a circular economy?", "options": {"A": "To increase production speed", "B": "To reduce waste and reuse resources", "C": "To create disposable products", "D": "To follow a traditional linear model"}, "correct": "B"},
            {"passage": "Cognitive dissonance is the mental discomfort experienced by a person who holds two or more contradictory beliefs or values. To reduce this discomfort, people may change their beliefs, justify their behavior, or deny new information. This psychological phenomenon plays a significant role in decision-making and attitude change.", "question": "How might a person resolve cognitive dissonance?", "options": {"A": "By seeking out more contradictory information", "B": "By ignoring the discomfort", "C": "By changing their beliefs or justifying their actions", "D": "By pointing out contradictions in others"}, "correct": "C"},
            {"passage": "The increasing automation of labor markets presents both opportunities and profound challenges. While automation can boost productivity and create new types of jobs, it also threatens to displace workers in routine-based occupations. This necessitates a proactive approach to reskilling and upskilling the workforce to adapt to the new economic landscape.", "question": "What is a necessary response to the challenge of automation?", "options": {"A": "Banning all new automation technologies", "B": "Focusing only on creating new jobs", "C": "Training workers with new skills", "D": "Ignoring the effects on the workforce"}, "correct": "C"},
            {"passage": "Confirmation bias is the tendency to search for, interpret, favor, and recall information in a way that confirms one's preexisting beliefs. This cognitive bias is a significant impediment to objective reasoning, as it leads individuals to hold on to false beliefs even when presented with contrary evidence.", "question": "What is the main effect of confirmation bias?", "options": {"A": "It helps people change their minds easily.", "B": "It encourages objective reasoning.", "C": "It makes people hold on to their existing beliefs.", "D": "It makes people question everything."}, "correct": "C"},
            {"passage": "The gig economy, characterized by short-term contracts and freelance work, has grown substantially. Proponents argue it offers flexibility and autonomy for workers. Critics, however, point to the lack of job security, benefits, and social protections that traditional employment provides.", "question": "What is a major criticism of the gig economy?", "options": {"A": "It offers too much flexibility.", "B": "It is not growing fast enough.", "C": "Workers lack job security and benefits.", "D": "It is a form of traditional employment."}, "correct": "C"},
        ],
        "C2": [
            {"passage": "The Sapir-Whorf hypothesis posits that the structure of a language affects its speakers' worldview or cognition. The 'strong' version, linguistic determinism, suggests language dictates thought, while the 'weak' version, linguistic relativity, proposes that language merely influences it. While linguistic determinism is largely discredited, the extent of linguistic relativity remains a subject of scholarly debate.", "question": "What does the 'strong' version of the Sapir-Whorf hypothesis suggest?", "options": {"A": "Language has a minor influence on thought.", "B": "Thought is independent of language.", "C": "Language determines the way we think.", "D": "Cognition is universal across all cultures."}, "correct": "C"},
            {"passage": "In quantum mechanics, Schrödinger's cat is a thought experiment that illustrates the paradox of quantum superposition. A hypothetical cat may be considered simultaneously both alive and dead as a result of its fate being linked to a random subatomic event that may or may not occur. The paradox is resolved when an observation is made, forcing the quantum state to collapse into one definite state.", "question": "In the thought experiment, what causes the cat's state to become definite?", "options": {"A": "The passage of time", "B": "The cat's own actions", "C": "A random subatomic event", "D": "The act of observation"}, "correct": "D"},
            {"passage": "Utilitarianism is an ethical theory that determines right from wrong by focusing on outcomes. It is a form of consequentialism. The most ethical choice is the one that will produce the greatest good for the greatest number of people. However, it is often criticized for the difficulty in predicting all consequences and for potentially neglecting individual rights.", "question": "What is a common criticism of utilitarianism?", "options": {"A": "It focuses too much on individual rights.", "B": "It is not a form of consequentialism.", "C": "It is difficult to foresee all outcomes.", "D": "It seeks the good of the few."}, "correct": "C"},
            {"passage": "The philosophical concept of 'qualia' refers to subjective, conscious experiences. For example, the redness of a red object or the pain of a headache are qualia. The 'hard problem of consciousness' is the question of how and why we have these subjective experiences, and it remains one of the most significant unsolved problems in neuroscience and philosophy.", "question": "What does 'qualia' refer to?", "options": {"A": "Objective, physical properties of objects", "B": "Subjective, personal conscious experiences", "C": "Unconscious brain processes", "D": "A solved problem in neuroscience"}, "correct": "B"},
            {"passage": "Epigenetics is the study of heritable changes in gene expression that do not involve changes to the underlying DNA sequence. These changes are influenced by factors like age, environment, and lifestyle. Epigenetic modifications can affect health and disease and are potentially reversible, opening new avenues for medical treatment.", "question": "What is a key characteristic of epigenetic changes?", "options": {"A": "They change the fundamental DNA sequence.", "B": "They are not influenced by the environment.", "C": "They are permanent and irreversible.", "D": "They can alter gene activity without changing the DNA itself."}, "correct": "D"},
        ],
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

LISTENING_SCENARIOS = {
    "en": {
        "A1": [
            {"scenario": "You hear someone say: 'Hello, my name is Sarah. I am from Canada. Nice to meet you.'", "question": "Where is Sarah from?", "options": {"A": "Canada", "B": "America", "C": "England", "D": "Australia"}, "correct": "A"},
            {"scenario": "A waiter says: 'Here is your coffee. That will be three dollars.'", "question": "How much is the coffee?", "options": {"A": "Two dollars", "B": "Three dollars", "C": "Four dollars", "D": "It's free"}, "correct": "B"},
            {"scenario": "Someone asks: 'What time is it?' You hear the reply: 'It is nine o'clock.'", "question": "What is the time?", "options": {"A": "Seven o'clock", "B": "Eight o'clock", "C": "Nine o'clock", "D": "Ten o'clock"}, "correct": "C"},
            {"scenario": "You hear: 'The weather is sunny today. It's a beautiful day.'", "question": "How is the weather?", "options": {"A": "Rainy", "B": "Cloudy", "C": "Snowy", "D": "Sunny"}, "correct": "D"},
            {"scenario": "A shop assistant says: 'Can I help you?' A customer replies: 'Yes, I'm looking for a red sweater.'", "question": "What is the customer looking for?", "options": {"A": "A blue shirt", "B": "A red sweater", "C": "Green pants", "D": "A yellow hat"}, "correct": "B"},
        ],
        "A2": [
            {"scenario": "You hear an announcement: 'The train to Manchester will depart from platform 3 at 2:30 PM. Please have your tickets ready.'", "question": "What time does the train leave?", "options": {"A": "2:00 PM", "B": "2:30 PM", "C": "3:00 PM", "D": "3:30 PM"}, "correct": "B"},
            {"scenario": "A person asks you: 'Excuse me, where is the nearest bank?' You hear a reply: 'Go straight for two blocks and turn left. It's on your right.'", "question": "Where is the bank after turning left?", "options": {"A": "On the left", "B": "Straight ahead", "C": "On the right", "D": "Behind you"}, "correct": "C"},
            {"scenario": "On the phone, you hear: 'Hi, can I speak to Tom? This is Jane. I'm calling about the party on Saturday.'", "question": "Why is Jane calling?", "options": {"A": "To invite Tom to a party", "B": "To talk about the party", "C": "To cancel the party", "D": "To ask about Tom's health"}, "correct": "B"},
            {"scenario": "At a store, you hear: 'These shoes are on sale for fifty dollars. They were seventy-five dollars before.'", "question": "How much do the shoes cost now?", "options": {"A": "Seventy-five dollars", "B": "Fifty dollars", "C": "Twenty-five dollars", "D": "One hundred dollars"}, "correct": "B"},
            {"scenario": "A weather forecast says: 'It will be cloudy in the morning, but expect heavy rain in the afternoon.'", "question": "What will the weather be like in the afternoon?", "options": {"A": "Sunny", "B": "Cloudy", "C": "Heavy rain", "D": "Snowy"}, "correct": "C"},
        ],
        "B1": [
            {"scenario": "You hear a voicemail: 'Hi, this is Mark. I'm calling to confirm our meeting for this Friday at 10 AM. We'll be discussing the quarterly budget report. Please let me know if that time still works for you.'", "question": "What is the main purpose of the call?", "options": {"A": "To cancel the meeting", "B": "To change the meeting time", "C": "To confirm the meeting details", "D": "To discuss the report now"}, "correct": "C"},
            {"scenario": "In a news report, you hear: 'The city council has approved the plan to build a new public library. Construction is expected to begin early next year and will take approximately 18 months to complete.'", "question": "How long will the construction of the library take?", "options": {"A": "One year", "B": "18 months", "C": "Next year", "D": "Six months"}, "correct": "B"},
            {"scenario": "You hear a tour guide say: 'On your left, you will see the famous art museum, which was built in the 19th century. We won't be going inside today, but we will stop for photos.'", "question": "What will the tour group do at the museum?", "options": {"A": "Go inside and see the art", "B": "Skip it completely", "C": "Stop to take pictures", "D": "Have lunch there"}, "correct": "C"},
            {"scenario": "A doctor tells a patient: 'You need to take this medicine twice a day, once in the morning and once at night, for seven days. Make sure you take it with food.'", "question": "How should the patient take the medicine?", "options": {"A": "Once a day", "B": "Without food", "C": "For three days", "D": "Twice a day with food"}, "correct": "D"},
            {"scenario": "You hear an advertisement: 'Are you tired of cooking every night? Try our new meal delivery service! Healthy, delicious meals delivered right to your door. Visit our website for a 20% discount on your first order.'", "question": "What is being advertised?", "options": {"A": "A new restaurant", "B": "A cooking class", "C": "A grocery store", "D": "A meal delivery service"}, "correct": "D"},
        ],
        "B2": [
            {"scenario": "You hear part of a lecture: 'The primary cause of the industrial revolution was not a single event, but rather a confluence of factors, including technological innovation, access to resources, and new economic theories.'", "question": "What does the speaker say was the cause of the industrial revolution?", "options": {"A": "A single, major event", "B": "Only technological innovation", "C": "A combination of different factors", "D": "New economic theories alone"}, "correct": "C"},
            {"scenario": "On a podcast, a speaker says: 'While many people believe multitasking is an efficient way to get more done, research suggests the opposite. Switching between tasks can decrease productivity by up to 40%.'", "question": "What does the research suggest about multitasking?", "options": {"A": "It is a very efficient skill.", "B": "It can significantly reduce productivity.", "C": "It helps in getting more done.", "D": "It is a myth and doesn't exist."}, "correct": "B"},
            {"scenario": "In a job interview, an interviewer asks: 'Can you describe a situation where you had to work under pressure and how you handled it?'", "question": "What is the interviewer asking about?", "options": {"A": "The candidate's educational background", "B": "The candidate's hobbies", "C": "The candidate's ability to handle stress", "D": "The candidate's salary expectations"}, "correct": "C"},
            {"scenario": "You hear a customer complaining: 'I've been waiting for my order for over 45 minutes. This level of service is simply unacceptable. I would like to speak to a manager immediately.'", "question": "What is the customer's main complaint?", "options": {"A": "The food is too expensive.", "B": "The restaurant is too noisy.", "C": "The wait time for the order is too long.", "D": "The manager is not available."}, "correct": "C"},
            {"scenario": "A radio host says: 'The government has announced new environmental regulations aimed at reducing plastic waste. These measures include a ban on single-use plastic bags and higher taxes on plastic packaging.'", "question": "What is the purpose of the new regulations?", "options": {"A": "To increase plastic production", "B": "To reduce plastic waste", "C": "To lower taxes on packaging", "D": "To encourage the use of plastic bags"}, "correct": "B"},
        ],
        "C1": [
            {"scenario": "You hear a critic reviewing a film: 'Despite its visually stunning cinematography, the film is ultimately undermined by a convoluted plot and underdeveloped characters. The narrative fails to provide any coherent emotional arc, leaving the audience disengaged.'", "question": "What is the critic's main issue with the film?", "options": {"A": "The visual effects were poor.", "B": "The story was confusing and the characters were weak.", "C": "The emotional arc was too predictable.", "D": "The cinematography was uninspired."}, "correct": "B"},
            {"scenario": "A financial analyst reports: 'Given the current market volatility, we are advising clients to diversify their portfolios and hedge against inflation by investing in commodities, rather than concentrating solely on equities.'", "question": "What advice is the analyst giving?", "options": {"A": "To sell all investments immediately.", "B": "To invest only in the stock market.", "C": "To spread investments across different assets.", "D": "To ignore the current market volatility."}, "correct": "C"},
            {"scenario": "You hear a scientist explaining a concept: 'The primary difference between correlation and causation is that correlation is simply a relationship where two things occur together, whereas causation implies that one event is the direct result of another.'", "question": "What is the key distinction between correlation and causation?", "options": {"A": "They are the same thing.", "B": "Correlation means one event causes another.", "C": "Causation implies a direct cause-and-effect link.", "D": "Causation is just a simple relationship."}, "correct": "C"},
            {"scenario": "A politician states: 'The proposed legislation, while well-intentioned, may have unforeseen and detrimental consequences for small businesses. We must conduct a more thorough impact assessment before proceeding.'", "question": "What is the politician's concern about the legislation?", "options": {"A": "It is not well-intentioned.", "B": "It will not affect small businesses.", "C": "It might have negative effects that haven't been considered.", "D": "It should be passed immediately without changes."}, "correct": "C"},
            {"scenario": "A university professor says: 'To plagiarize is to present someone else's work or ideas as your own, with or without their consent. It is a serious academic offense with severe penalties.'", "question": "What is plagiarism?", "options": {"A": "Citing your sources correctly.", "B": "Using your own original ideas.", "C": "Asking for permission to use someone's work.", "D": "Using someone else's work without proper credit."}, "correct": "D"},
        ],
        "C2": [
            {"scenario": "In an academic debate, a philosopher states: 'The ontological argument for the existence of God, while elegant in its formulation, is often criticized for being a mere linguistic trick—a tautology that presupposes its own conclusion rather than proving it from empirical evidence.'", "question": "What is the main criticism of the ontological argument mentioned?", "options": {"A": "It is too complex for most people to understand.", "B": "It relies too heavily on scientific evidence.", "C": "It is a form of circular reasoning.", "D": "It is not an elegant argument."}, "correct": "C"},
            {"scenario": "A literary scholar explains: 'The author's use of stream of consciousness is not merely a stylistic flourish; it is integral to the novel's thematic exploration of subjectivity, blurring the lines between the protagonist's internal monologue and external reality.'", "question": "According to the scholar, what is the function of the stream of consciousness technique in the novel?", "options": {"A": "It is just a decorative stylistic choice.", "B": "It simplifies the plot for the reader.", "C": "It is essential to exploring the theme of subjectivity.", "D": "It separates the character's thoughts from reality."}, "correct": "C"},
            {"scenario": "A legal expert comments: 'The principle of habeas corpus is a fundamental bulwark against unlawful detention. It ensures that an authority must provide a valid reason to a court for a person's imprisonment.'", "question": "What does habeas corpus protect against?", "options": {"A": "Unlawful imprisonment without justification.", "B": "Excessive fines.", "C": "Freedom of speech violations.", "D": "Unfair trials."}, "correct": "A"},
            {"scenario": "An economist argues: 'Keynesian economics advocates for government intervention to mitigate recessionary downturns, primarily through fiscal policy. This is in stark contrast to classical theories which champion laissez-faire, or minimal government interference.'", "question": "How does Keynesian economics differ from classical theories?", "options": {"A": "It argues for less government intervention.", "B": "It supports government action to manage economic slumps.", "C": "It focuses only on monetary policy.", "D": "It is identical to laissez-faire principles."}, "correct": "B"},
            {"scenario": "A historian remarks: 'The Treaty of Westphalia in 1648 is often cited as the origin of the modern state system, establishing the principle of state sovereignty and non-interference in the domestic affairs of other states.'", "question": "What key principle was established by the Treaty of Westphalia?", "options": {"A": "The creation of a single global government.", "B": "The right of one state to interfere in another's affairs.", "C": "The sovereignty and independence of states.", "D": "The abolition of all national borders."}, "correct": "C"},
        ],
        # ... (다른 언어들도 추가 가능)
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
        """무료 데이터셋 초기화 (비동기 방식으로 최적화)"""
        if self.is_initialized:
            return

        logger.info("📥 무료 어휘 데이터 다운로드 중...")

        # 공개 어휘 목록 URL들
        vocab_urls = {
            "common_words": "https://raw.githubusercontent.com/first20hours/google-10000-english/master/20k.txt",
            "oxford_3000": "https://raw.githubusercontent.com/hackergrrl/oxford-3000/master/oxford-3000.json"
        }

        # 비동기 클라이언트를 생성
        async with httpx.AsyncClient() as client:
            # 각 URL에 대한 요청 작업을 리스트에 담습니다.
            tasks = {name: client.get(url, timeout=10) for name, url in vocab_urls.items()}

            # 모든 요청을 동시에 보내고 응답을 기다립니다.
            responses = await asyncio.gather(*tasks.values(), return_exceptions=True)

            # 응답 결과를 순서대로 처리
            for (name, response) in zip(tasks.keys(), responses):
                if isinstance(response, Exception):
                    logger.error(f"❌ {name} 오류: {response}")
                    continue

                if response.status_code == 200:
                    try:
                        if name == "oxford_3000":
                            self.vocabulary_cache[name] = response.json()
                        else:
                            words = response.text.strip().split('\n')
                            self.vocabulary_cache[name] = [word.strip().lower() for word in words if word.strip()]

                        logger.info(f"✅ {name}: {len(self.vocabulary_cache[name])} 단어")
                    except Exception as e:
                        logger.error(f"❌ {name} 데이터 처리 오류 : {e}")
                else:
                    logger.warning(f"❌ {name} 다운로드 실패 : {response.status_code}")

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

            async with httpx.AsyncClient() as client:
                response = await client.get(def_url, params=params, timeout=5)

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

        for _ in range(min(count, len(level_words), 10)):
            if not level_words: continue

            word = random.choice(level_words)

            if skill == "vocabulary":
                question = await self._create_vocab_question(word, level)
            elif skill == "grammar":
                question = await self._create_grammar_question(word, level)
            elif skill == "reading":
                question = await self._create_reading_question(level)
            else: # skill == 'listening'
                # ▼▼▼ [2단계] 이 부분을 원래 함수 호출로 수정합니다. ▼▼▼
                question = await self._create_listening_question(level)

            questions.append(question)

        return questions

    async def _get_level_words(self, level: str) -> List[str]:
        """특정 레벨의 단어들 추출"""

        # oxford_3000 단어 목록이 있으면 우선적으로 사용
        words_source = self.vocabulary_cache.get("oxford_3000") or self.vocabulary_cache.get("common_words")

        if not words_source:
            return ["important", "necessary", "possible", "available", "comfortable"]

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
        end = min(end, len(words_source))

        level_words = []
        if start < len(words_source):
            level_words = words_source[start:end]

        # 단어가 부족할 경우, 리스트 뒷부분에서 가져옴
        if len(level_words) < 5:
            level_words.extend(words_source[-50:])

        return level_words[:50]  # 상위 50개만

    async def _create_vocab_question(self, word: str, level: str) -> Dict:
        """어휘 문제 생성 (C1, C2 레벨 및 문제 대량 추가)"""

        # API 의존성을 제거하고, 미리 정의된 고품질 문제 목록을 사용합니다.
        predefined_questions = {
            "A1": [
                {"word": "apple", "q": "What is an 'apple'?", "correct": "A type of fruit", "decoys": ["A type of animal", "A color", "A piece of clothing"]},
                {"word": "book", "q": "What is a 'book'?", "correct": "Something you read", "decoys": ["Something you eat", "Something you wear", "Something you drive"]},
                {"word": "water", "q": "What is 'water'?", "correct": "A clear liquid that you drink", "decoys": ["A type of food", "A piece of furniture", "A kind of music"]},
                {"word": "house", "q": "What is a 'house'?", "correct": "A building where people live", "decoys": ["A place where you study", "A type of car", "An animal"]},
                {"word": "eat", "q": "What does 'eat' mean?", "correct": "To put food in your mouth and swallow it", "decoys": ["To sleep", "To run", "To read"]},
                {"word": "big", "q": "What does 'big' mean?", "correct": "Large in size", "decoys": ["Small in size", "Red in color", "Very fast"]},
                {"word": "school", "q": "What is a 'school'?", "correct": "A place where children go to learn", "decoys": ["A place to buy food", "A place to watch movies", "A place to play sports"]},
                {"word": "car", "q": "What is a 'car'?", "correct": "A vehicle with four wheels that you drive", "decoys": ["A vehicle that flies", "A vehicle for water", "A type of bicycle"]},
                {"word": "friend", "q": "Who is a 'friend'?", "correct": "A person you know well and like", "decoys": ["A person who teaches you", "A member of your family", "A doctor"]},
                {"word": "dog", "q": "What is a 'dog'?", "correct": "A common animal kept as a pet", "decoys": ["A large bird", "A type of fish", "An insect"]},
            ],
            "A2": [
                {"word": "family", "q": "What is a 'family'?", "correct": "A group of people who are related", "decoys": ["A place where you work", "A type of food", "A kind of sport"]},
                {"word": "happy", "q": "What is the meaning of 'happy'?", "correct": "Feeling or showing pleasure", "decoys": ["Feeling tired or sleepy", "Feeling angry", "Feeling hungry"]},
                {"word": "library", "q": "What is a 'library'?", "correct": "A place with books you can read or borrow", "decoys": ["A place to buy clothes", "A place to eat", "A place to swim"]},
                {"word": "travel", "q": "What does 'travel' mean?", "correct": "To go from one place to another", "decoys": ["To stay in one place", "To buy something", "To cook a meal"]},
                {"word": "job", "q": "What is a 'job'?", "correct": "The work a person does to earn money", "decoys": ["A hobby you do for fun", "A type of vacation", "A school subject"]},
                {"word": "expensive", "q": "What does 'expensive' mean?", "correct": "Costing a lot of money", "decoys": ["Costing very little money", "Very beautiful", "Easy to find"]},
                {"word": "weather", "q": "What is 'weather'?", "correct": "The condition of the air, such as sunny, rainy, or cold", "decoys": ["A feeling or emotion", "A type of building", "A style of music"]},
                {"word": "listen", "q": "What does 'listen' mean?", "correct": "To give attention to someone or something in order to hear them", "decoys": ["To look at something", "To speak loudly", "To touch something gently"]},
                {"word": "morning", "q": "What is the 'morning'?", "correct": "The early part of the day, from when the sun rises until noon", "decoys": ["The middle of the night", "The time after sunset", "A full 24-hour period"]},
                {"word": "beautiful", "q": "What does 'beautiful' mean?", "correct": "Very pleasing to the eyes", "decoys": ["Not attractive", "Very loud", "Difficult to understand"]},
            ],
            "B1": [
                {"word": "important", "q": "What does 'important' mean?", "correct": "Of great significance or value", "decoys": ["Not interesting at all", "Very small and tiny", "Difficult to see"]},
                {"word": "difficult", "q": "What does 'difficult' mean?", "correct": "Needing much effort or skill to do", "decoys": ["Very easy and simple", "Sweet to the taste", "Bright and full of light"]},
                {"word": "environment", "q": "What does 'environment' mean?", "correct": "The natural world, as a whole or in a particular geographical area", "decoys": ["A single person's opinion", "The political system of a country", "A type of technology"]},
                {"word": "opinion", "q": "What is an 'opinion'?", "correct": "A view or judgment formed about something, not necessarily based on fact", "decoys": ["A proven fact that everyone accepts", "A law made by the government", "A scientific theory"]},
                {"word": "advantage", "q": "What is an 'advantage'?", "correct": "A condition or circumstance that puts one in a favorable position", "decoys": ["A serious problem or difficulty", "A final result or outcome", "A simple mistake"]},
                {"word": "improve", "q": "What does 'improve' mean?", "correct": "To make or become better", "decoys": ["To make something worse", "To keep something the same", "To destroy something completely"]},
                {"word": "culture", "q": "What is 'culture'?", "correct": "The customs, arts, and social institutions of a particular nation or group", "decoys": ["The science of farming", "A single, isolated event", "The system of money in a country"]},
                {"word": "communicate", "q": "What does 'communicate' mean?", "correct": "To share or exchange information, news, or ideas", "decoys": ["To hide or keep something secret", "To compete against someone", "To travel alone"]},
                {"word": "society", "q": "What is 'society'?", "correct": "People living together in a more or less ordered community", "decoys": ["An individual person", "A small group of animals", "A company that sells products"]},
                {"word": "probably", "q": "What does 'probably' mean?", "correct": "Almost certainly; as far as one knows or can tell", "decoys": ["Definitely not; with no chance", "With absolute certainty", "Rarely or almost never"]},
            ],
            "B2": [
                {"word": "achieve", "q": "What does 'achieve' mean?", "correct": "To succeed in finishing something or reaching an aim", "decoys": ["To start something new", "To forget something", "To wait for a long time"]},
                {"word": "opportunity", "q": "What is an 'opportunity'?", "correct": "A time or set of circumstances that makes it possible to do something", "decoys": ["A serious problem or obstacle", "A feeling of deep sadness", "A final, unchangeable decision"]},
                {"word": "consequence", "q": "What is a 'consequence'?", "correct": "A result or effect of an action or condition", "decoys": ["The reason or cause of something", "An unrelated, random event", "A plan for the future"]},
                {"word": "efficient", "q": "What does 'efficient' mean?", "correct": "Working in a well-organized way, without wasting time or energy", "decoys": ["Working slowly and without a plan", "Complicated and difficult to use", "Beautiful but not functional"]},
                {"word": "influence", "q": "What does 'influence' mean?", "correct": "The capacity to have an effect on the character or behavior of someone", "decoys": ["To force someone to do something against their will", "To observe without interacting", "To measure something accurately"]},
                {"word": "significant", "q": "What does 'significant' mean?", "correct": "Sufficiently great or important to be worthy of attention", "decoys": ["Common and ordinary", "Small and irrelevant", "Temporary and quickly forgotten"]},
                {"word": "complex", "q": "What does 'complex' mean?", "correct": "Consisting of many different and connected parts", "decoys": ["Simple and easy to understand", "Having a single purpose", "Empty or hollow inside"]},
                {"word": "strategy", "q": "What is a 'strategy'?", "correct": "A plan of action designed to achieve a long-term or overall aim", "decoys": ["A spontaneous, unplanned action", "A detailed report of past events", "A natural, unchangeable characteristic"]},
                {"word": "potential", "q": "What does 'potential' mean?", "correct": "Having the capacity to develop into something in the future", "decoys": ["Fully realized and complete", "Impossible to change or improve", "Based on past failures"]},
                {"word": "analyze", "q": "What does 'analyze' mean?", "correct": "To examine something in detail to understand it or explain it", "decoys": ["To guess the meaning without evidence", "To summarize briefly", "To ignore the details"]},
            ],
            "C1": [
                {"word": "ubiquitous", "q": "What does 'ubiquitous' mean?", "correct": "Present, appearing, or found everywhere", "decoys": ["Extremely rare and hard to find", "Only existing in one specific place", "Invisible to the naked eye"]},
                {"word": "mitigate", "q": "What does 'mitigate' mean?", "correct": "To make something bad less severe, serious, or painful", "decoys": ["To make a situation worse or more intense", "To ignore a problem completely", "To celebrate a successful outcome"]},
                {"word": "meticulous", "q": "What does 'meticulous' mean?", "correct": "Showing great attention to detail; very careful and precise", "decoys": ["Careless and disorganized", "Quick and impulsive", "Broad and general"]},
                {"word": "ambiguous", "q": "What does 'ambiguous' mean?", "correct": "Open to more than one interpretation; having a double meaning", "decoys": ["Clear and easy to understand", "Stated in a very direct way", "Containing no useful information"]},
                {"word": "synthesize", "q": "What does 'synthesize' mean?", "correct": "To combine a number of things into a coherent whole", "decoys": ["To break something down into its parts", "To repeat information exactly as it was heard", "To remove unnecessary components"]},
                {"word": "empirical", "q": "What does 'empirical' mean?", "correct": "Based on observation or experience rather than theory", "decoys": ["Based on abstract principles or theory", "Based on personal feelings or beliefs", "Based on a fictional story"]},
                {"word": "advocate", "q": "What does it mean to 'advocate' for something?", "correct": "To publicly recommend or support", "decoys": ["To publicly criticize or oppose", "To remain neutral and undecided", "To investigate secretly"]},
                {"word": "discrepancy", "q": "What is a 'discrepancy'?", "correct": "A lack of compatibility or similarity between two or more facts", "decoys": ["A perfect match or agreement", "A widely accepted theory", "A minor, unimportant detail"]},
                {"word": "volatile", "q": "What does 'volatile' mean?", "correct": "Liable to change rapidly and unpredictably, especially for the worse", "decoys": ["Stable and unchanging", "Slow and predictable", "Safe and secure"]},
                {"word": "inference", "q": "What is an 'inference'?", "correct": "A conclusion reached on the basis of evidence and reasoning", "decoys": ["A directly stated fact", "A random guess", "A personal opinion without evidence"]},
            ],
            "C2": [
                {"word": "ephemeral", "q": "What does 'ephemeral' mean?", "correct": "Lasting for a very short time", "decoys": ["Lasting forever", "Occurring once a year", "Difficult to remember"]},
                {"word": "dichotomy", "q": "What is a 'dichotomy'?", "correct": "A division or contrast between two things that are represented as being opposed", "decoys": ["A situation where many things are combined", "A complete agreement between two parties", "A long and complicated process"]},
                {"word": "serendipity", "q": "What is 'serendipity'?", "correct": "The occurrence of events by chance in a happy or beneficial way", "decoys": ["A carefully planned discovery", "An unfortunate accident", "A predictable outcome"]},
                {"word": "pulchritudinous", "q": "What does 'pulchritudinous' mean?", "correct": "Characterized by great physical beauty and appeal", "decoys": ["Having a strong and unpleasant smell", "Extremely intelligent", "Morally corrupt or wicked"]},
                {"word": "esoteric", "q": "What does 'esoteric' mean?", "correct": "Intended for or likely to be understood by only a small number of people", "decoys": ["Widely known and understood by everyone", "Simple and easy to learn", "Related to outdoor activities"]},
                {"word": "cacophony", "q": "What is a 'cacophony'?", "correct": "A harsh, discordant mixture of sounds", "decoys": ["A pleasant and harmonious melody", "Complete and utter silence", "A single, clear musical note"]},
                {"word": "juxtaposition", "q": "What is 'juxtaposition'?", "correct": "The fact of two things being seen or placed close together with contrasting effect", "decoys": ["Placing two similar things far apart", "A state of perfect balance and harmony", "The chronological order of events"]},
                {"word": "obfuscate", "q": "What does 'obfuscate' mean?", "correct": "To deliberately make something unclear or harder to understand", "decoys": ["To clarify or explain in simple terms", "To make something transparent", "To publicly announce a discovery"]},
                {"word": "paradigm", "q": "What is a 'paradigm'?", "correct": "A typical example or pattern of something; a model", "decoys": ["A logical contradiction or puzzle", "A minor exception to a rule", "A random, unorganized collection"]},
                {"word": "sycophant", "q": "What is a 'sycophant'?", "correct": "A person who acts obsequiously toward someone important to gain advantage", "decoys": ["A person who is a strong and fair leader", "An honest critic who speaks their mind", "Someone who prefers to work alone"]},
            ],
        }

        # 해당 레벨의 문제 목록을 가져옵니다. 없으면 바로 아래 레벨을 순차적으로 탐색합니다.
        level_order = ["C2", "C1", "B2", "B1", "A2", "A1"]
        questions_for_level = []
        try:
            current_index = level_order.index(level)
            for i in range(current_index, len(level_order)):
                level_to_try = level_order[i]
                if level_to_try in predefined_questions:
                    questions_for_level = predefined_questions[level_to_try]
                    break
        except ValueError:
            questions_for_level = predefined_questions["A2"] # 기본값

        if not questions_for_level:
            questions_for_level = predefined_questions["A2"]

        # 문제 목록에서 무작위로 하나를 선택합니다.
        chosen_q = random.choice(questions_for_level)

        # 정답과 오답 선택지를 합쳐서 무작위로 섞습니다.
        correct_def = chosen_q["correct"]
        options_list = [correct_def] + chosen_q["decoys"]
        random.shuffle(options_list)

        # 섞인 목록을 기반으로 최종 선택지와 정답 알파벳을 생성합니다.
        correct_answer_char = chr(65 + options_list.index(correct_def))
        final_options = {chr(65 + i): opt for i, opt in enumerate(options_list)}

        return {
            "question_id": f"vocab_{level}_{chosen_q['word']}_{random.randint(1000, 9999)}",
            "skill": "vocabulary",
            "level": level,
            "question": chosen_q["q"],
            "options": final_options,
            "correct_answer": correct_answer_char,
            "explanation": f"'{chosen_q['word']}' means: {correct_def}",
            "word": chosen_q["word"],
            "source": "local_predefined_vocab_questions_v2" # 소스 버전 업데이트
        }

    async def _create_grammar_question(self, word: str, level: str) -> Dict:
        """문법 문제 생성 (수정: 전역 문제 목록을 사용하도록 변경)"""
        try:
            # 영어('en') 문법 템플릿 목록을 가져옵니다.
            lang_templates = GRAMMAR_TEMPLATES.get("en", {})

            # 해당 레벨의 문제 목록을 가져오되, 없으면 하위 레벨에서 찾습니다.
            level_order = ["C2", "C1", "B2", "B1", "A2", "A1"]
            templates_for_level = []
            try:
                current_index = level_order.index(level)
                for i in range(current_index, len(level_order)):
                    level_to_try = level_order[i]
                    if level_to_try in lang_templates and lang_templates[level_to_try]:
                        templates_for_level = lang_templates[level_to_try]
                        break
            except ValueError:
                pass

            # 최종적으로도 없으면 A1 레벨 문제를 사용합니다.
            if not templates_for_level:
                templates_for_level = lang_templates.get("A1", [])

            if not templates_for_level:
                raise Exception(f"No grammar templates found for level {level} or any fallback.")

            chosen_template = random.choice(templates_for_level)

            # 선택지와 정답 목록을 합쳐서 무작위로 섞기
            options_list = list(chosen_template["options"].values())
            correct_answer_value = chosen_template["options"][chosen_template["correct"]]

            # 만약 정답이 이미 options_list에 있다면 그대로 사용, 없다면 추가
            if correct_answer_value not in options_list:
                # 이 경우는 데이터 포맷이 다르므로 다른 방식으로 처리
                options_list = list(chosen_template["options"].values())

            random.shuffle(options_list)

            # 섞인 목록에서 정답이 몇 번째에 있는지 확인 (A=0, B=1, ...)
            correct_answer_char = chr(65 + options_list.index(correct_answer_value))

            # 최종 선택지 딕셔너리 생성
            options = {chr(65 + i): opt for i, opt in enumerate(options_list)}

            return {
                "question_id": f"grammar_{level}_{word}_{random.randint(1000, 9999)}",
                "skill": "grammar",
                "level": level,
                "question": chosen_template["template"],
                "options": options,
                "correct_answer": correct_answer_char,
                "explanation": f"이 문제는 '{chosen_template['point']}' 문법 규칙을 테스트합니다.",
                "grammar_point": chosen_template['point'],
                "source": "global_grammar_templates_v2" # 소스 버전 업데이트
            }
        except Exception as e:
            logger.error(f"문법 문제 생성 중 오류 발생: {e}")
            return self._get_fallback_question("grammar", level, random.randint(1, 100))


    async def _create_reading_question(self, level: str) -> Dict:
        """읽기 문제 생성 (수정: 전역 문제 목록을 사용하도록 변경)"""

        try:
            # 영어('en') 지문 목록을 가져옵니다.
            lang_passages = READING_PASSAGES.get("en", {})

            # 해당 레벨의 문제 목록을 가져오되, 없으면 하위 레벨에서 찾습니다.
            level_order = ["C2", "C1", "B2", "B1", "A2", "A1"]
            passages_for_level = []
            try:
                current_index = level_order.index(level)
                for i in range(current_index, len(level_order)):
                    level_to_try = level_order[i]
                    if level_to_try in lang_passages and lang_passages[level_to_try]:
                        passages_for_level = lang_passages[level_to_try]
                        break
            except ValueError:
                pass

            # 최종적으로도 없으면 A1 레벨 문제를 사용합니다.
            if not passages_for_level:
                passages_for_level = lang_passages.get("A1", [])

            if not passages_for_level:
                raise Exception(f"No reading passages found for level {level} or any fallback.")

            passage_data = random.choice(passages_for_level)

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
                "source": "curated_passages_v2" # 소스 버전 업데이트
            }
        except Exception as e:
            logger.error(f"읽기 문제 생성 중 오류 발생: {e}")
            # 오류 발생 시를 위한 대체 문제를 반환합니다.
            return self._get_fallback_question("reading", level, random.randint(1, 100))

    async def _create_listening_question(self, level: str) -> Dict:
        """듣기 문제 생성 (전역 목록 및 무작위 선택 적용)"""

        try:
            # 1. 파일 상단에 정의된 전역 LISTENING_SCENARIOS 목록에서 영어('en') 시나리오를 가져옵니다.
            lang_scenarios = LISTENING_SCENARIOS.get("en", {})

            # 2. 해당 레벨의 문제 목록을 가져옵니다. 없으면 A1을 기본값으로 사용합니다.
            level_scenarios = lang_scenarios.get(level, lang_scenarios.get("A1", []))

            if not level_scenarios:
                # 안전 장치: A1 목록조차 없는 경우를 대비합니다.
                level_scenarios = lang_scenarios.get("A1", [])
                if not level_scenarios:
                    raise Exception("No listening scenarios found for any level.")

            # 3. 해당 레벨의 문제 목록에서 무작위로 시나리오 하나를 선택합니다.
            scenario = random.choice(level_scenarios)

            return {
                "question_id": f"listening_{level}_{random.randint(1000, 9999)}",
                "skill": "listening",
                "level": level,
                "audio_scenario": scenario["scenario"],
                "question": scenario["question"],
                "options": scenario["options"],
                "correct_answer": scenario["correct"],
                "explanation": "오디오 정보를 바탕으로 답했습니다.",
                "source": "listening_scenarios_v3"
            }
        except Exception as e:
            logger.error(f"듣기 문제 생성 중 오류 발생: {e}")
            # 오류 발생 시를 위한 최소한의 대체 문제를 반환합니다.
            return {
                "question_id": "fallback_listen_error", "skill": "listening", "level": level,
                "audio_scenario": "There was an error.", "question": "Could not load question.",
                "options": {"A": "OK"}, "correct_answer": "A", "explanation": "Error"
            }

class LevelTestService:
    """API 기반 개선된 레벨 테스트 서비스"""

    def __init__(self):
        """초기화"""

        # --- OpenAI 설정 ---
        self.openai_api_key = os.getenv("OPENAI_API_KEY")

        # API 키가 있는지 확인하고, 있다면 타임아웃을 포함하여 클라이언트를 생성합니다.
        if self.openai_api_key:
            self.openai_client = OpenAI(api_key=self.openai_api_key, timeout=20.0)
        else:
            self.openai_client = None
            # 개발 중에는 키가 없는 경우를 쉽게 알 수 있도록 경고 메시지를 추가하는 것이 좋습니다.
            print("경고: OPENAI_API_KEY 환경 변수가 설정되지 않았습니다. OpenAI 클라이언트를 초기화할 수 없습니다.")

        # --- 외부 API 서비스 ---
        self.quick_api = QuickStartLanguageAPI()

        # --- 세션 관리 ---
        self.active_sessions = {}

        # --- CEFR 레벨 정의 ---
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
        self._initialization_task = None

    async def _ensure_initialized(self):
        """데이터셋 초기화 보장"""
        if self._initialization_task is None:
            # create_task를 사용하여 여러 요청이 동시에 들어와도 초기화는 한 번만 실행되도록 보장
            self._initialization_task = asyncio.create_task(self.quick_api.initialize_datasets())
        await self._initialization_task

    # ▼▼▼ [수정 1/4] 새로운 헬퍼 함수 추가 ▼▼▼
    def _get_question_identifier(self, question: Dict) -> str:
        """문제 내용 기반의 고유 식별자를 생성합니다."""
        if not question:
            return f"invalid_{random.randint(1000, 9999)}"

        skill = question.get("skill", "unknown")

        # 각 유형별로 내용의 일부를 조합하여 식별자 생성
        if skill == "vocabulary":
            return f"vocab_{question.get('word', '')}"
        elif skill == "grammar":
            return f"grammar_{question.get('question', '')}"
        elif skill == "reading":
            passage = question.get('passage', '')
            return f"reading_{passage[:50]}" # 지문의 일부 사용
        elif skill == "listening":
            scenario = question.get('audio_scenario', '')
            return f"listening_{scenario[:50]}" # 시나리오의 일부 사용

        # 예외 처리
        return f"unknown_{question.get('question_id', random.randint(1000, 9999))}"

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
                "language": language_code,
                "start_time": datetime.now().isoformat(),
                "current_question": 0,
                "total_questions": 15,
                "estimated_level": "A2",
                "confidence": 0.1,
                "responses": [],
                "skill_scores": {"vocabulary": [], "grammar": [], "reading": [], "listening": []},
                "completed": False,
                "question_sources": [],
                "used_question_identifiers": set(),  # ▼▼▼ [수정 2/4] 출제된 문제 기록용 Set 추가
            }

            self.active_sessions[session_id] = session_data

            # 첫 번째 문제 생성
            first_question = await self._generate_unique_question(session_data, "vocabulary", "A2")

            session_data["current_question_data"] = first_question

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
                "total_questions": session_data["total_questions"],
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

    async def _generate_unique_question(self, session: Dict, skill: str, level: str) -> Dict:
        """중복되지 않는 문제를 생성하는 래퍼 함수"""
        for _ in range(10):  # 최대 10번 재시도
            question = await self._generate_question(session, skill, level)
            identifier = self._get_question_identifier(question)

            if identifier not in session["used_question_identifiers"]:
                session["used_question_identifiers"].add(identifier)
                return question

        logger.warning(f"고유 문제 생성 실패: {session['session_id']}. 중복 문제가 출제될 수 있습니다.")
        # 10번 시도 후에도 실패하면 마지막으로 생성된 문제라도 반환
        return await self._generate_question(session, skill, level)

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
        """언어별 듣기 문제 생성 (전역 목록 및 무작위 선택 적용)"""

        try:
            # 전역으로 선언된 LISTENING_SCENARIOS 목록을 사용합니다.
            lang_scenarios = LISTENING_SCENARIOS.get(language, LISTENING_SCENARIOS["en"])

            # 해당 레벨의 문제 목록을 가져옵니다.
            level_scenarios = lang_scenarios.get(level, lang_scenarios.get("A1", []))

            if not level_scenarios:
                return self._get_fallback_question_multilang("listening", level, language, 1)

            # 목록에서 무작위로 시나리오 하나를 선택합니다.
            scenario = random.choice(level_scenarios)

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
                "source": "listening_scenarios_v2"
            }
        except Exception as e:
            logger.error(f"듣기 문제 생성 오류: {e}")
            return self._get_fallback_question_multilang("listening", level, language, 1)

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
            if (session["current_question"] >= session["total_questions"]):

                final_result = await self._complete_test(session)
                session["completed"] = True
                session["final_result"] = final_result

                return {
                    "success": True,
                    "status": "completed",
                    "final_result": final_result
                }

            else:
                # ▼▼▼ [수정 4/4] 다음 문제 생성 시, 중복 방지 래퍼 함수를 호출 ▼▼▼
                next_skill = ""
                if session.get("is_mini_test"):
                    next_skill = session["mini_test_skills_order"][session["current_question"]]
                else:
                    next_skill = self._determine_next_skill(session)

                next_level = session["estimated_level"]
                # 기존 _generate_question 대신 _generate_unique_question 호출
                next_question = await self._generate_unique_question(session, next_skill, next_level)

                session["current_question_data"] = next_question

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
            return { "success": False, "error": f"답변 처리 중 오류가 발생했습니다: {str(e)}" }

    async def _evaluate_answer(self, question_id: str, answer: str, session: Dict) -> Dict:
        """답변 평가 (전면 수정)"""
        try:
            # 1. 세션에 저장된 현재 문제의 전체 데이터를 가져옵니다.
            question_data = session.get("current_question_data")

            # 2. 문제 ID가 일치하는지, 정답 정보가 있는지 확인합니다.
            if not question_data or question_data.get("question_id") != question_id:
                # 정보가 없으면 0점 처리
                is_correct = False
                score = 0.0
            else:
                # 3. 저장된 정답과 사용자의 답을 비교하여 채점합니다.
                correct_answer = question_data.get("correct_answer")
                is_correct = answer.upper() == correct_answer.upper()
                score = 100.0 if is_correct else 0.0

            return {
                "question_id": question_id,
                "user_answer": answer,
                "correct": is_correct,
                "score": score, # 올바른 점수(100 또는 0)를 반환
                "skill": self._get_question_skill(question_id, session),
                "level": session["estimated_level"],
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"답변 평가 중 심각한 오류 발생: {e}")
            # 예외 발생 시 안전하게 0점 처리
            return {
                "question_id": question_id, "user_answer": answer, "correct": False,
                "score": 0, "skill": "unknown", "level": session["estimated_level"],
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

            try:
                # 1. .env 파일 등에서 백엔드 서버 주소를 가져옵니다.
                backend_url = os.getenv("BACKEND_URL", "http://127.0.0.1:8001")

                # 2. 백엔드로 보낼 데이터를 준비합니다. (사용자 이메일과 최종 레벨)
                update_data = {
                    "email": session["user_id"], # AI 서버의 user_id가 사용자의 이메일
                    "assessed_level": final_level
                }

                print(f"\n--- [디버그] 백엔드 레벨 업데이트 요청 ---")
                print(f"  - 요청 주소: {backend_url}/auth/update-level")
                print(f"  - 전송 데이터: {update_data}")

                print(f"백엔드({backend_url}/auth/update-level)로 레벨 업데이트 요청 전송...")

                # 3. 백엔드의 /auth/update-level API로 POST 요청을 보냅니다.
                response = requests.post(
                    f"{backend_url}/auth/update-level",
                    json=update_data,
                    timeout=10
                )

                # 4. 요청 성공 여부를 로그로 남깁니다.
                if response.status_code == 200:
                    print("✅ 백엔드에 레벨 정보 업데이트 성공")
                else:
                    print(f"🔥 백엔드 레벨 정보 업데이트 실패: {response.status_code} - {response.text}")

            except Exception as http_error:
                print(f"🔥 백엔드로 레벨 정보 전송 중 네트워크 오류 발생: {http_error}")

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

    async def start_mini_vocab_test(self, user_id: str, language: str = "english") -> Dict:
        """4문제 유형별 미니 레벨 테스트를 시작합니다."""
        try:
            await self._ensure_initialized()

            language_code = "en" # 현재 미니 테스트는 영어만 지원한다고 가정

            session_id = f"mini_test_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            # ▼▼▼ [추가] 4가지 스킬의 순서를 무작위로 섞습니다. ▼▼▼
            skills_to_test = ["vocabulary", "grammar", "reading", "listening"]
            random.shuffle(skills_to_test)

            # 미니 테스트용 세션 데이터 수정
            session_data = {
                "session_id": session_id,
                "user_id": user_id,
                "language": language_code,
                "start_time": datetime.now().isoformat(),
                "current_question": 0,
                "total_questions": 4, # 3문제에서 4문제로 변경
                "estimated_level": "B1",
                "confidence": 0.1,
                "responses": [],
                "skill_scores": {"vocabulary": [], "grammar": [], "reading": [], "listening": []},
                "completed": False,
                "question_sources": [],
                "is_mini_test": True, # 미니 테스트임을 명시하는 플래그 추가
                "mini_test_skills_order": skills_to_test, # 무작위로 섞인 스킬 순서 저장
                "used_question_identifiers": set(), # ▼▼▼ [수정 3/4] 미니 테스트에도 Set 추가
            }

            self.active_sessions[session_id] = session_data

            # 섞인 순서에 따라 첫 번째 문제를 생성합니다.
            first_skill = skills_to_test[0]
            first_question = await self._generate_unique_question(session_data, first_skill, "B1")

            # 정답 채점을 위해 문제 정보를 세션에 저장합니다.
            session_data["current_question_data"] = first_question

            logger.info(f"4-Question Mini Level Test started: {session_id}")

            return {
                "success": True,
                "session_id": session_id,
                "total_questions": 4, # 프론트엔드에 총 4문제임을 알려줍니다.
                "current_question": first_question,
            }

        except Exception as e:
            logger.error(f"미니 테스트 시작 오류: {e}")
            return {"success": False, "error": f"미니 테스트를 시작할 수 없습니다: {str(e)}"}

# 전역 서비스 인스턴스
level_test_service = LevelTestService()

class GrammarPracticeService:
    """
    Grammar learning and practice service.
    """
    def __init__(self):
        self.active_sessions = {}
        # We can reuse the question generation logic from the LevelTestService's API helper
        self.question_generator = QuickStartLanguageAPI()
        self._initialization_task = None

    async def _ensure_initialized(self):
        """Ensure the underlying question generator's datasets are ready."""
        if self._initialization_task is None:
            self._initialization_task = asyncio.create_task(self.question_generator.initialize_datasets())
        await self._initialization_task

    async def start_grammar_session(self, user_id: str, language: str, level: str) -> Dict:
        """Starts a new grammar practice session."""
        await self._ensure_initialized()
        session_id = f"grammar_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # [DEBUG] Get a random word for the first question
        level_words = await self.question_generator._get_level_words(level)
        logger.info(f"[DEBUG-START] Found {len(level_words)} words for level {level}.")

        first_word = random.choice(level_words) if level_words else "important"
        logger.info(f"[DEBUG-START] Selected first word: '{first_word}'")

        first_question = await self.question_generator._create_grammar_question(first_word, level)
        logger.info(f"[DEBUG-START] Generated first question: \"{first_question.get('question')}\"")

        self.active_sessions[session_id] = {
            "user_id": user_id,
            "language": language,
            "level": level,
            "current_question": first_question,
            "score": 0,
            "question_count": 0
        }

        logger.info(f"Grammar session started: {session_id} for user {user_id}")
        return {
            "success": True,
            "session_id": session_id,
            "question": first_question
        }

    async def submit_grammar_answer(self, session_id: str, question_id: str, user_answer: str) -> Dict:
        """Submits an answer and gets the next question."""
        if session_id not in self.active_sessions:
            return {"success": False, "error": "Session not found."}

        session = self.active_sessions[session_id]
        current_question = session["current_question"]

        if question_id != current_question.get("question_id"):
            return {"success": False, "error": "Question ID mismatch."}

        is_correct = user_answer.upper() == current_question.get("correct_answer", "").upper()

        if is_correct:
            session["score"] += 1
        session["question_count"] += 1

        # [DEBUG] Generate the next question with a new random word
        level_words = await self.question_generator._get_level_words(session["level"])
        logger.info(f"[DEBUG-NEXT] Found {len(level_words)} words for level {session['level']}.")

        next_word = random.choice(level_words) if level_words else "practice"
        logger.info(f"[DEBUG-NEXT] Randomly selected next word: '{next_word}'")

        next_question = await self.question_generator._create_grammar_question(next_word, session["level"])
        logger.info(f"[DEBUG-NEXT] Generated next question: \"{next_question.get('question')}\"")

        session["current_question"] = next_question

        logger.info(f"Answer submitted for session {session_id}. Correct: {is_correct}")

        return {
            "success": True,
            "is_correct": is_correct,
            "explanation": current_question.get("explanation", "No explanation available."),
            "correct_answer": current_question.get("correct_answer"),
            "next_question": next_question
        }

# Instantiate the new service
grammar_practice_service = GrammarPracticeService()
