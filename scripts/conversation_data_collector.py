"""
무료 여행 상황별 실제 언어 데이터 수집 시스템
- 상황: 공항, 레스토랑, 호텔, 길거리
- 언어: 영어 (나중에 다른 언어 추가 가능)
- 100% 실제 데이터만 수집 (임의 생성 금지)
- 무료 소스만 사용: Reddit, 교육사이트, Cornell Movie Corpus
"""

import asyncio
import aiohttp
import json
import os
import re
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

class TravelSituation(Enum):
    AIRPORT = "airport"
    RESTAURANT = "restaurant" 
    HOTEL = "hotel"
    STREET = "street"

class Language(Enum):
    ENGLISH = "en"
    # 나중에 추가: KOREAN = "ko", JAPANESE = "ja", etc.

@dataclass
class RealConversationData:
    """실제 수집된 대화 데이터"""
    situation: TravelSituation
    language: Language
    source: str
    dialogue_text: str
    context: str
    participants: List[str]
    difficulty_level: str
    timestamp: str
    metadata: Dict[str, Any]

class FreeTravelDataCollector:
    """무료 여행 언어 데이터 수집기 (3개 소스만)"""
    
    def __init__(self, target_language: Language = Language.ENGLISH):
        self.target_language = target_language
        self.collected_data: List[RealConversationData] = []
        
        # 무료 API 키들만
        self.api_keys = {
            'reddit_client_id': os.getenv('REDDIT_CLIENT_ID'),
            'reddit_client_secret': os.getenv('REDDIT_CLIENT_SECRET'),
        }
        
        # 상황별 키워드 매핑
        self.situation_keywords = {
            TravelSituation.AIRPORT: {
                'primary': ['airport', 'flight', 'gate', 'boarding', 'check-in', 'departure', 'arrival'],
                'secondary': ['passport', 'luggage', 'security', 'terminal', 'customs', 'immigration'],
                'participants': ['passenger', 'agent', 'staff', 'traveler', 'tourist']
            },
            TravelSituation.RESTAURANT: {
                'primary': ['restaurant', 'menu', 'order', 'food', 'waiter', 'server', 'dining'],
                'secondary': ['reservation', 'table', 'bill', 'tip', 'chef', 'kitchen', 'meal'],
                'participants': ['customer', 'guest', 'waiter', 'server', 'host', 'chef']
            },
            TravelSituation.HOTEL: {
                'primary': ['hotel', 'room', 'reception', 'check-in', 'check-out', 'reservation'],
                'secondary': ['lobby', 'key', 'wifi', 'breakfast', 'service', 'concierge'],
                'participants': ['guest', 'receptionist', 'staff', 'concierge', 'housekeeping']
            },
            TravelSituation.STREET: {
                'primary': ['street', 'direction', 'map', 'lost', 'help', 'way', 'location'],
                'secondary': ['bus', 'subway', 'taxi', 'walk', 'turn', 'block', 'intersection'],
                'participants': ['tourist', 'local', 'stranger', 'passerby', 'guide']
            }
        }
    
    # =================================================================
    # 메인 수집 함수 (무료 소스만)
    # =================================================================
    
    async def collect_all_travel_data(self) -> List[RealConversationData]:
        """모든 여행 상황의 실제 데이터 수집 - 무료 소스만"""
        
        print(f"🌍 무료 여행 언어 데이터 수집 시작 - 언어: {self.target_language.value}")
        print("💰 사용 소스: Reddit, 교육사이트, Cornell Movie Corpus (100% 무료)")
        print("=" * 60)
        
        # 모든 상황에 대해 병렬로 데이터 수집
        collection_tasks = []
        
        for situation in TravelSituation:
            print(f"\n📍 {situation.value.upper()} 상황 데이터 수집 중...")
            
            # 무료 소스 3개만 사용
            tasks = [
                self._collect_reddit_real_experiences(situation),
                self._collect_educational_real_content(situation),
                self._collect_movie_subtitle_data(situation)
            ]
            
            collection_tasks.extend(tasks)
        
        # 모든 작업 병렬 실행
        print("\n🔄 무료 소스에서 병렬 데이터 수집 중...")
        results = await asyncio.gather(*collection_tasks, return_exceptions=True)
        
        # 결과 처리
        total_collected = 0
        for result in results:
            if isinstance(result, list):
                self.collected_data.extend(result)
                total_collected += len(result)
            elif isinstance(result, Exception):
                print(f"⚠️ 수집 중 오류: {result}")
        
        print(f"\n✅ 총 {total_collected}개의 실제 대화 데이터 수집 완료!")
        
        # 데이터 정제 및 검증
        validated_data = self._validate_and_clean_data()
        
        return validated_data
    
    # =================================================================
    # Reddit 실제 경험담 수집
    # =================================================================
    
    async def _collect_reddit_real_experiences(self, situation: TravelSituation) -> List[RealConversationData]:
        """Reddit에서 실제 여행 경험담 수집"""
        
        if not (self.api_keys['reddit_client_id'] and self.api_keys['reddit_client_secret']):
            print(f"⚠️ Reddit API 키가 없습니다 - {situation.value} 스킵")
            return []
        
        # 상황별 관련 서브레딧
        subreddit_map = {
            TravelSituation.AIRPORT: ['travel', 'solotravel', 'aviation', 'flight'],
            TravelSituation.RESTAURANT: ['travel', 'food', 'solotravel', 'backpacking'],
            TravelSituation.HOTEL: ['travel', 'hotels', 'solotravel', 'hospitality'],
            TravelSituation.STREET: ['travel', 'solotravel', 'backpacking', 'AskReddit']
        }
        
        real_experiences = []
        
        try:
            import praw
            
            reddit = praw.Reddit(
                client_id=self.api_keys['reddit_client_id'],
                client_secret=self.api_keys['reddit_client_secret'],
                user_agent='TravelLanguageLearning/1.0'
            )
            
            for subreddit_name in subreddit_map[situation]:
                subreddit = reddit.subreddit(subreddit_name)
                
                # 상황 관련 검색어
                search_terms = self.situation_keywords[situation]['primary'][:3]
                
                for term in search_terms:
                    try:
                        for submission in subreddit.search(f"{term} conversation", limit=5):
                            # 게시물 본문에서 실제 대화 추출
                            if submission.selftext and len(submission.selftext) > 100:
                                dialogue_data = self._extract_reddit_dialogue(
                                    submission.title,
                                    submission.selftext,
                                    situation,
                                    subreddit_name
                                )
                                if dialogue_data:
                                    real_experiences.append(dialogue_data)
                            
                            # 댓글에서도 실제 경험 수집
                            submission.comments.replace_more(limit=0)
                            for comment in submission.comments.list()[:10]:
                                if self._is_real_travel_experience(comment.body, situation):
                                    comment_data = RealConversationData(
                                        situation=situation,
                                        language=self.target_language,
                                        source=f"reddit_{subreddit_name}_comment",
                                        dialogue_text=comment.body,
                                        context=f"Reddit comment on: {submission.title[:50]}...",
                                        participants=self._extract_participants(comment.body, situation),
                                        difficulty_level=self._assess_difficulty_level(comment.body),
                                        timestamp=datetime.now().isoformat(),
                                        metadata={
                                            'subreddit': subreddit_name,
                                            'post_title': submission.title
                                        }
                                    )
                                    real_experiences.append(comment_data)
                    
                    except Exception as e:
                        print(f"Reddit 검색 오류 ({term}): {e}")
                        continue
        
        except ImportError:
            print("⚠️ PRAW 설치 필요: pip install praw")
            return []
        except Exception as e:
            print(f"❌ Reddit {situation.value} 수집 오류: {e}")
        
        print(f"💬 Reddit {situation.value}: {len(real_experiences)}개 수집")
        return real_experiences
    
    def _extract_reddit_dialogue(self, title: str, content: str, situation: TravelSituation, subreddit: str) -> Optional[RealConversationData]:
        """Reddit 게시물에서 실제 대화 추출"""
        
        # 실제 대화가 포함된 경우만
        dialogue_indicators = ['"', "'", 'said', 'told', 'asked', 'replied', 'he said', 'she said']
        
        if any(indicator in content for indicator in dialogue_indicators):
            # 상황 관련 키워드 확인
            situation_keywords = self.situation_keywords[situation]['primary']
            if any(keyword in content.lower() for keyword in situation_keywords):
                
                return RealConversationData(
                    situation=situation,
                    language=self.target_language,
                    source=f"reddit_{subreddit}_post",
                    dialogue_text=content,
                    context=f"Reddit post: {title}",
                    participants=self._extract_participants(content, situation),
                    difficulty_level=self._assess_difficulty_level(content),
                    timestamp=datetime.now().isoformat(),
                    metadata={
                        'subreddit': subreddit,
                        'post_title': title
                    }
                )
        
        return None
    
    # =================================================================
    # 교육 자료 실제 대화 수집
    # =================================================================
    
    async def _collect_educational_real_content(self, situation: TravelSituation) -> List[RealConversationData]:
        """교육 웹사이트에서 실제 대화 예시 수집"""
        
        # 신뢰할 수 있는 영어 교육 사이트들
        educational_urls = {
            TravelSituation.AIRPORT: [
                'https://www.englishclub.com/english-for-work/airport-english.htm',
                'https://www.fluentu.com/blog/english/english-airport-conversation/'
            ],
            TravelSituation.RESTAURANT: [
                'https://www.englishclub.com/english-for-work/restaurant-english.htm',
                'https://www.fluentu.com/blog/english/restaurant-english/'
            ],
            TravelSituation.HOTEL: [
                'https://www.englishclub.com/english-for-work/hotel-english.htm',
                'https://www.fluentu.com/blog/english/hotel-english/'
            ],
            TravelSituation.STREET: [
                'https://www.englishclub.com/vocabulary/directions.htm',
                'https://www.fluentu.com/blog/english/asking-for-directions-english/'
            ]
        }
        
        real_educational_content = []
        
        try:
            from bs4 import BeautifulSoup
            
            async with aiohttp.ClientSession() as session:
                for url in educational_urls.get(situation, []):
                    try:
                        async with session.get(url) as response:
                            if response.status == 200:
                                html = await response.text()
                                soup = BeautifulSoup(html, 'html.parser')
                                
                                # 대화 예시 추출
                                dialogue_elements = soup.find_all(['div', 'p'], class_=lambda x: x and ('dialogue' in x.lower() or 'conversation' in x.lower()))
                                
                                for element in dialogue_elements:
                                    text = element.get_text().strip()
                                    if self._is_structured_dialogue(text):
                                        dialogue_data = RealConversationData(
                                            situation=situation,
                                            language=self.target_language,
                                            source=f"educational_{url.split('//')[1].split('/')[0]}",
                                            dialogue_text=text,
                                            context=f"Educational content from {url}",
                                            participants=self._extract_participants(text, situation),
                                            difficulty_level="beginner",  # 교육 자료는 보통 초급
                                            timestamp=datetime.now().isoformat(),
                                            metadata={
                                                'source_url': url,
                                                'content_type': 'educational_example'
                                            }
                                        )
                                        real_educational_content.append(dialogue_data)
                        
                        await asyncio.sleep(2)  # 웹사이트 부하 방지
                        
                    except Exception as e:
                        print(f"교육 사이트 수집 오류 ({url}): {e}")
                        continue
        
        except ImportError:
            print("⚠️ BeautifulSoup 설치 필요: pip install beautifulsoup4")
        
        print(f"📚 Educational {situation.value}: {len(real_educational_content)}개 수집")
        return real_educational_content
    
    # =================================================================
    # 영화 자막 실제 대화 수집
    # =================================================================
    
    async def _collect_movie_subtitle_data(self, situation: TravelSituation) -> List[RealConversationData]:
        """영화 자막에서 상황별 실제 대화 수집"""
        
        # Cornell Movie Dialogs Corpus 사용
        movie_dialogues = await self._collect_cornell_movie_dialogues(situation)
        
        print(f"🎬 Movies {situation.value}: {len(movie_dialogues)}개 수집")
        return movie_dialogues
    
    async def _collect_cornell_movie_dialogues(self, situation: TravelSituation) -> List[RealConversationData]:
        """Cornell Movie Dialogs에서 상황별 대화 추출"""
        
        # 이미 다운로드된 Cornell 데이터가 있는지 확인
        cornell_file = 'cornell_data/cornell movie-dialogs corpus/movie_lines.txt'
        
        if not os.path.exists(cornell_file):
            print(f"⚠️ Cornell Movie Dialogs 데이터가 없습니다 - {situation.value} 스킵")
            print(f"💡 다운로드: http://www.cs.cornell.edu/~cristian/Cornell_Movie-Dialogs_Corpus.html")
            return []
        
        movie_dialogues = []
        situation_keywords = self.situation_keywords[situation]['primary']
        
        try:
            with open(cornell_file, 'r', encoding='iso-8859-1') as f:
                lines = f.readlines()
                
                for line in lines:
                    parts = line.split(' +++$+++ ')
                    if len(parts) >= 5:
                        dialogue_text = parts[4].strip()
                        
                        # 상황 관련 키워드 필터링
                        if any(keyword in dialogue_text.lower() for keyword in situation_keywords):
                            movie_data = RealConversationData(
                                situation=situation,
                                language=self.target_language,
                                source=f"cornell_movie_corpus",
                                dialogue_text=dialogue_text,
                                context=f"Movie dialogue from Cornell corpus",
                                participants=['character1', 'character2'],
                                difficulty_level=self._assess_difficulty_level(dialogue_text),
                                timestamp=datetime.now().isoformat(),
                                metadata={
                                    'movie_id': parts[2] if len(parts) > 2 else 'unknown',
                                    'character_id': parts[1] if len(parts) > 1 else 'unknown'
                                }
                            )
                            movie_dialogues.append(movie_data)
        
        except Exception as e:
            print(f"Cornell 데이터 처리 오류: {e}")
        
        return movie_dialogues
    
    # =================================================================
    # 데이터 처리 및 유틸리티 함수들
    # =================================================================
    
    def _is_real_travel_experience(self, text: str, situation: TravelSituation) -> bool:
        """실제 여행 경험담인지 확인"""
        experience_indicators = ['i was', 'when i', 'at the', 'the staff', 'they said', 'i asked']
        situation_keywords = self.situation_keywords[situation]['primary']
        
        return (len(text) > 50 and 
                any(indicator in text.lower() for indicator in experience_indicators) and
                any(keyword in text.lower() for keyword in situation_keywords))
    
    def _is_structured_dialogue(self, text: str) -> bool:
        """구조화된 대화인지 확인"""
        dialogue_indicators = [':', 'A:', 'B:', 'Customer:', 'Staff:', 'Tourist:', 'Local:']
        return any(indicator in text for indicator in dialogue_indicators)
    
    def _extract_participants(self, text: str, situation: TravelSituation) -> List[str]:
        """대화 참여자 추출"""
        participants = self.situation_keywords[situation]['participants']
        found_participants = []
        
        for participant in participants:
            if participant in text.lower():
                found_participants.append(participant)
        
        return found_participants if found_participants else ['person1', 'person2']
    
    def _assess_difficulty_level(self, text: str) -> str:
        """텍스트 난이도 평가"""
        word_count = len(text.split())
        avg_word_length = sum(len(word) for word in text.split()) / word_count if word_count > 0 else 0
        
        if word_count < 30 and avg_word_length < 5:
            return "beginner"
        elif word_count < 80 and avg_word_length < 6:
            return "intermediate"
        else:
            return "advanced"
    
    def _validate_and_clean_data(self) -> List[RealConversationData]:
        """데이터 검증 및 정제"""
        
        validated_data = []
        
        for data in self.collected_data:
            # 최소 길이 확인
            if len(data.dialogue_text.strip()) < 20:
                continue
            
            # 중복 제거
            if any(existing.dialogue_text == data.dialogue_text for existing in validated_data):
                continue
            
            # 언어 확인 (간단한 방법)
            if self._is_target_language(data.dialogue_text):
                validated_data.append(data)
        
        print(f"🔍 데이터 검증 완료: {len(validated_data)}개 유효한 데이터")
        return validated_data
    
    def _is_target_language(self, text: str) -> bool:
        """텍스트가 목표 언어인지 확인"""
        # 간단한 영어 확인 (실제로는 더 정교한 언어 감지 필요)
        english_indicators = ['the', 'and', 'is', 'are', 'was', 'were', 'have', 'has']
        return any(indicator in text.lower() for indicator in english_indicators)
    
    # =================================================================
    # 데이터 저장 및 내보내기
    # =================================================================
    
    def save_collected_data(self, filename: Optional[str] = None) -> str:
        """수집된 데이터를 JSON 파일로 저장"""
        
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"free_travel_conversations_{self.target_language.value}_{timestamp}.json"
        
        # 데이터를 JSON 직렬화 가능한 형태로 변환
        export_data = {
            'metadata': {
                'collection_date': datetime.now().isoformat(),
                'target_language': self.target_language.value,
                'total_conversations': len(self.collected_data),
                'sources_used': ['reddit', 'educational_websites', 'cornell_movie_corpus'],
                'cost': 'FREE',
                'situations': list(set(data.situation.value for data in self.collected_data)),
                'sources': list(set(data.source for data in self.collected_data))
            },
            'conversations': []
        }
        
        # 상황별로 데이터 정리
        situation_stats = {}
        for data in self.collected_data:
            situation = data.situation.value
            if situation not in situation_stats:
                situation_stats[situation] = 0
            situation_stats[situation] += 1
            
            conversation_entry = {
                'id': len(export_data['conversations']) + 1,
                'situation': data.situation.value,
                'language': data.language.value,
                'source': data.source,
                'dialogue': data.dialogue_text,
                'context': data.context,
                'participants': data.participants,
                'difficulty_level': data.difficulty_level,
                'timestamp': data.timestamp,
                'metadata': data.metadata
            }
            export_data['conversations'].append(conversation_entry)
        
        export_data['metadata']['situation_breakdown'] = situation_stats
        
        # 파일 저장
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 데이터 저장 완료: {filename}")
        print(f"📊 상황별 데이터 수:")
        for situation, count in situation_stats.items():
            print(f"   - {situation}: {count}개")
        
        return filename
    
    def export_for_ai_training(self, output_dir: str = "training_data") -> Dict[str, str]:
        """AI 학습용 포맷으로 데이터 내보내기"""
        
        import os
        os.makedirs(output_dir, exist_ok=True)
        
        exported_files = {}
        
        # 상황별로 분리하여 저장
        for situation in TravelSituation:
            situation_data = [
                data for data in self.collected_data 
                if data.situation == situation
            ]
            
            if not situation_data:
                continue
            
            # AI 학습용 포맷으로 변환
            training_format = {
                'dataset_info': {
                    'situation': situation.value,
                    'language': self.target_language.value,
                    'total_samples': len(situation_data),
                    'purpose': 'travel_conversation_training',
                    'cost': 'FREE'
                },
                'training_data': []
            }
            
            for data in situation_data:
                # 대화를 입력-출력 쌍으로 변환
                dialogue_lines = data.dialogue_text.split('\n')
                
                for i in range(0, len(dialogue_lines) - 1, 2):
                    if i + 1 < len(dialogue_lines):
                        training_sample = {
                            'input': dialogue_lines[i].strip(),
                            'output': dialogue_lines[i + 1].strip(),
                            'context': {
                                'situation': situation.value,
                                'participants': data.participants,
                                'difficulty': data.difficulty_level,
                                'source': data.source
                            }
                        }
                        training_format['training_data'].append(training_sample)
            
            # 파일 저장
            filename = f"{output_dir}/{situation.value}_free_training_{self.target_language.value}.json"
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(training_format, f, indent=2, ensure_ascii=False)
            
            exported_files[situation.value] = filename
            print(f"📁 {situation.value} 학습 데이터: {filename}")
        
        return exported_files
    
    def generate_statistics_report(self) -> Dict[str, Any]:
        """수집된 데이터의 통계 보고서 생성"""
        
        if not self.collected_data:
            return {"error": "수집된 데이터가 없습니다."}
        
        # 기본 통계
        total_conversations = len(self.collected_data)
        
        # 상황별 통계
        situation_stats = {}
        for situation in TravelSituation:
            count = len([d for d in self.collected_data if d.situation == situation])
            situation_stats[situation.value] = count
        
        # 소스별 통계
        source_stats = {}
        for data in self.collected_data:
            source_type = data.source.split('_')[0]  # 소스 타입 추출
            source_stats[source_type] = source_stats.get(source_type, 0) + 1
        
        # 난이도별 통계
        difficulty_stats = {}
        for data in self.collected_data:
            difficulty_stats[data.difficulty_level] = difficulty_stats.get(data.difficulty_level, 0) + 1
        
        # 텍스트 길이 통계
        text_lengths = [len(data.dialogue_text.split()) for data in self.collected_data]
        avg_length = sum(text_lengths) / len(text_lengths) if text_lengths else 0
        
        report = {
            'collection_summary': {
                'total_conversations': total_conversations,
                'target_language': self.target_language.value,
                'collection_date': datetime.now().isoformat(),
                'average_text_length': round(avg_length, 1),
                'cost': 'FREE'
            },
            'situation_breakdown': situation_stats,
            'source_breakdown': source_stats,
            'difficulty_breakdown': difficulty_stats,
            'quality_metrics': {
                'min_length': min(text_lengths) if text_lengths else 0,
                'max_length': max(text_lengths) if text_lengths else 0,
                'median_length': sorted(text_lengths)[len(text_lengths)//2] if text_lengths else 0
            }
        }
        
        return report


# =================================================================
# 사용 예시 및 메인 실행 함수
# =================================================================

async def main():
    """메인 실행 함수 - 무료 데이터 수집 과정"""
    
    print("🌍 무료 여행 맞춤 언어 학습 데이터 수집기")
    print("=" * 60)
    print("상황: 공항, 레스토랑, 호텔, 길거리")
    print("언어: 영어 (나중에 다른 언어 추가 가능)")
    print("원칙: 100% 실제 데이터만 수집")
    print("💰 비용: 무료 (Reddit + 교육사이트 + Cornell)")
    print("=" * 60)
    
    # 수집기 초기화
    collector = FreeTravelDataCollector(Language.ENGLISH)
    
    # 모든 상황의 실제 데이터 수집
    collected_data = await collector.collect_all_travel_data()
    
    # 수집 결과 요약
    if collected_data:
        print(f"\n🎉 무료 데이터 수집 완료!")
        
        # 통계 보고서 생성
        stats = collector.generate_statistics_report()
        print(f"\n📊 수집 통계:")
        print(f"   총 대화: {stats['collection_summary']['total_conversations']}개")
        print(f"   평균 길이: {stats['collection_summary']['average_text_length']} 단어")
        print(f"   💰 비용: {stats['collection_summary']['cost']}")
        
        print(f"\n📍 상황별 데이터:")
        for situation, count in stats['situation_breakdown'].items():
            print(f"   - {situation}: {count}개")
        
        print(f"\n📚 소스별 데이터:")
        for source, count in stats['source_breakdown'].items():
            print(f"   - {source}: {count}개")
        
        # 데이터 저장
        saved_file = collector.save_collected_data()
        
        # AI 학습용 데이터 내보내기
        print(f"\n🤖 AI 학습용 데이터 내보내기...")
        training_files = collector.export_for_ai_training()
        
        print(f"\n✅ 모든 작업 완료!")
        print(f"📁 원본 데이터: {saved_file}")
        print(f"📁 학습 데이터: {len(training_files)}개 파일 생성")
        
    else:
        print("❌ 수집된 데이터가 없습니다. API 키 설정을 확인하세요.")

def setup_free_api_keys():
    """무료 API 키 설정 가이드"""
    
    required_keys = {
        'REDDIT_CLIENT_ID': 'https://www.reddit.com/prefs/apps',
        'REDDIT_CLIENT_SECRET': 'https://www.reddit.com/prefs/apps',
    }
    
    print("🔑 필요한 무료 API 키 설정:")
    print("=" * 40)
    
    for key, url in required_keys.items():
        value = os.getenv(key)
        status = "✅ 설정됨" if value else "❌ 미설정"
        print(f"{key}: {status}")
        if not value:
            print(f"   발급 URL: {url}")
    
    print("\n💡 .env 파일에 API 키를 설정하세요:")
    print("REDDIT_CLIENT_ID=your_reddit_id_here")
    print("REDDIT_CLIENT_SECRET=your_reddit_secret_here")
    
    print("\n📋 무료 데이터 소스:")
    print("1. Reddit API - 무료 (실제 여행 경험담)")
    print("2. 교육 웹사이트 - 무료 (영어 학습 대화 예시)")
    print("3. Cornell Movie Corpus - 무료 (영화 대화 데이터)")

def download_cornell_data():
    """Cornell Movie Corpus 다운로드 가이드"""
    
    print("\n🎬 Cornell Movie Corpus 다운로드:")
    print("=" * 40)
    print("1. 웹사이트: http://www.cs.cornell.edu/~cristian/Cornell_Movie-Dialogs_Corpus.html")
    print("2. 다운로드: cornell movie-dialogs corpus.zip")
    print("3. 압축 해제: cornell_data/ 폴더에")
    print("4. 파일 위치: cornell_data/cornell movie-dialogs corpus/movie_lines.txt")
    print("\n💡 선택사항: Cornell 데이터 없이도 Reddit + 교육사이트로 수집 가능")

if __name__ == "__main__":
    print("🚀 무료 여행 언어 데이터 수집기 시작!")
    
    # 무료 API 키 확인
    setup_free_api_keys()
    
    # Cornell 데이터 가이드
    download_cornell_data()
    
    # 사용자 확인
    proceed = input("\n계속 진행하시겠습니까? (y/N): ")
    
    if proceed.lower() == 'y':
        # 필요한 라이브러리 설치 확인
        try:
            import aiohttp
            import praw
            from bs4 import BeautifulSoup
            
            # 메인 수집 실행
            asyncio.run(main())
            
        except ImportError as e:
            print(f"\n❌ 필수 라이브러리가 설치되지 않았습니다: {e}")
            print("다음 명령어로 설치하세요:")
            print("pip install aiohttp praw beautifulsoup4")
    else:
        print("👋 데이터 수집을 취소했습니다.")