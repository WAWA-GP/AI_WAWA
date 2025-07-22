# app/services/conversation_ai_service.py
# 실제 수집 데이터를 활용한 시나리오 기반 대화 AI

import json
import random
import re
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class ScenarioConversationService:
    """시나리오 기반 대화 서비스 - 수집된 실제 데이터 활용"""
    
    def __init__(self):
        self.conversation_scenarios = {}
        self.current_scenarios = {}  # session_id별 현재 시나리오
        self.load_collected_data()
        
    def load_collected_data(self):
        """수집된 대화 데이터를 시나리오로 변환"""
        
        try:
            # 수집한 JSON 파일 읽기
            with open('free_travel_conversations_en_20250722_161841.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 상황별로 대화 시나리오 분류
            for conversation in data['conversations']:
                situation = conversation['situation']
                
                if situation not in self.conversation_scenarios:
                    self.conversation_scenarios[situation] = {
                        'dialogues': [],
                        'common_phrases': [],
                        'scenarios': []
                    }
                
                # 실제 대화를 시나리오로 변환
                dialogue_text = conversation['dialogue']
                scenario = self._extract_scenario_from_dialogue(dialogue_text, situation)
                
                if scenario:
                    self.conversation_scenarios[situation]['scenarios'].append(scenario)
            
            # 기본 시나리오 추가 (데이터 없을 때 대비)
            self._add_default_scenarios()
            
            logger.info(f"시나리오 로드 완료: {len(self.conversation_scenarios)}개 상황")
            
        except FileNotFoundError:
            logger.warning("수집된 대화 파일을 찾을 수 없음. 기본 시나리오만 사용")
            self._add_default_scenarios()
        except Exception as e:
            logger.error(f"데이터 로드 오류: {e}")
            self._add_default_scenarios()
    
    def _extract_scenario_from_dialogue(self, dialogue_text: str, situation: str) -> Optional[Dict]:
        """실제 대화에서 시나리오 패턴 추출"""
        
        # 대화에서 주요 패턴 찾기
        patterns = {
            'airport': [
                r'check.?in|boarding|gate|flight|passport|luggage',
                r'departure|arrival|security|terminal|customs'
            ],
            'restaurant': [
                r'menu|order|food|table|reservation|bill',
                r'waiter|server|chef|meal|dish|drink'
            ],
            'hotel': [
                r'room|key|reception|check.?in|check.?out',
                r'service|wifi|breakfast|lobby|concierge'
            ],
            'street': [
                r'direction|way|map|lost|help|street',
                r'bus|subway|taxi|walk|turn|block'
            ]
        }
        
        situation_patterns = patterns.get(situation, [])
        
        # 패턴 매칭으로 관련도 확인
        relevance_score = 0
        for pattern in situation_patterns:
            matches = len(re.findall(pattern, dialogue_text.lower()))
            relevance_score += matches
        
        if relevance_score > 0:
            return {
                'dialogue': dialogue_text[:500],  # 처음 500자만
                'relevance_score': relevance_score,
                'key_phrases': self._extract_key_phrases(dialogue_text, situation),
                'difficulty': 'intermediate'  # 기본값
            }
        
        return None
    
    def _extract_key_phrases(self, text: str, situation: str) -> List[str]:
        """대화에서 핵심 표현 추출"""
        
        key_phrase_patterns = {
            'airport': [
                'check in', 'boarding pass', 'gate number', 'departure time',
                'passport please', 'luggage weight', 'window seat', 'aisle seat'
            ],
            'restaurant': [
                'table for', 'can I see the menu', 'I would like', 'check please',
                'is it spicy', 'what do you recommend', 'bill please', 'tip included'
            ],
            'hotel': [
                'reservation', 'room key', 'wifi password', 'checkout time',
                'room service', 'wake up call', 'extra towels', 'front desk'
            ],
            'street': [
                'how do I get to', 'where is', 'excuse me', 'turn left',
                'straight ahead', 'next to', 'across from', 'thank you'
            ]
        }
        
        phrases = key_phrase_patterns.get(situation, [])
        found_phrases = []
        
        for phrase in phrases:
            if phrase.lower() in text.lower():
                found_phrases.append(phrase)
        
        return found_phrases[:5]  # 최대 5개
    
    def start_scenario(
        self, 
        session_id: str, 
        situation: str,
        difficulty: str = "beginner"
    ) -> Dict[str, Any]:
        """새로운 시나리오 시작"""
        
        if situation not in self.conversation_scenarios:
            return {
                "success": False,
                "error": f"지원하지 않는 상황: {situation}"
            }
        
        # 난이도에 맞는 시나리오 선택
        scenarios = self.conversation_scenarios[situation]['scenarios']
        
        if not scenarios:
            # 기본 시나리오 사용
            scenario = self._get_default_scenario(situation, difficulty)
        else:
            # 수집된 데이터에서 랜덤 선택
            scenario = random.choice(scenarios)
        
        # 시나리오 구조화
        structured_scenario = self._create_scenario_structure(scenario, situation, difficulty)
        
        # 세션에 저장
        self.current_scenarios[session_id] = {
            'situation': situation,
            'difficulty': difficulty,
            'scenario': structured_scenario,
            'current_step': 0,
            'user_responses': [],
            'started_at': datetime.now().isoformat()
        }
        
        return {
            "success": True,
            "scenario_id": session_id,
            "situation": situation,
            "difficulty": difficulty,
            "scenario_title": structured_scenario['title'],
            "first_message": structured_scenario['steps'][0]['ai_message'],
            "expected_responses": structured_scenario['steps'][0]['expected_responses']
        }
    
    def _create_scenario_structure(self, base_scenario: Dict, situation: str, difficulty: str) -> Dict:
        """시나리오를 구조화된 대화 단계로 변환"""
        
        scenario_templates = {
            'airport': {
                'title': 'Airport Check-in',
                'steps': [
                    {
                        'step': 1,
                        'ai_message': 'Good morning! Welcome to the airport. How can I help you today?',
                        'expected_responses': ['I need to check in', 'Check in please', 'I have a flight'],
                        'feedback_tips': 'Try saying: "I need to check in for my flight"'
                    },
                    {
                        'step': 2,
                        'ai_message': 'May I see your passport and boarding pass?',
                        'expected_responses': ['Here you are', 'Sure, here it is', 'Of course'],
                        'feedback_tips': 'A polite way to respond: "Here you are" or "Of course"'
                    }
                ]
            },
            'restaurant': {
                'title': 'Restaurant Ordering',
                'steps': [
                    {
                        'step': 1,
                        'ai_message': 'Good evening! Welcome to our restaurant. Do you have a reservation?',
                        'expected_responses': ['Yes, under...', 'No, table for two please', 'I made a reservation'],
                        'feedback_tips': 'You can say: "Yes, under [your name]" or "Table for [number] please"'
                    },
                    {
                        'step': 2,
                        'ai_message': 'Right this way. Here are your menus. Can I get you something to drink?',
                        'expected_responses': ['Water please', 'Can I see the wine list', 'Coffee, please'],
                        'feedback_tips': 'Simple responses work: "Water please" or "Coffee, please"'
                    }
                ]
            }
        }
        
        # 템플릿에서 가져오거나 기본 구조 생성
        template = scenario_templates.get(situation, {
            'title': f'{situation.title()} Conversation',
            'steps': [
                {
                    'step': 1,
                    'ai_message': f'Hello! Let\'s practice {situation} conversation.',
                    'expected_responses': ['Hello', 'Hi', 'Good morning'],
                    'feedback_tips': 'Try greeting back politely'
                }
            ]
        })
        
        return template
    
    def process_user_response(
        self, 
        session_id: str, 
        user_message: str
    ) -> Dict[str, Any]:
        """사용자 응답 처리 및 다음 단계 진행"""
        
        if session_id not in self.current_scenarios:
            return {
                "success": False,
                "error": "활성 시나리오가 없습니다. 먼저 시나리오를 시작해주세요."
            }
        
        scenario_data = self.current_scenarios[session_id]
        current_step = scenario_data['current_step']
        scenario = scenario_data['scenario']
        
        # 현재 단계의 기대 응답과 비교
        if current_step < len(scenario['steps']):
            step_data = scenario['steps'][current_step]
            
            # 응답 분석
            feedback = self._analyze_user_response(
                user_message, 
                step_data['expected_responses'],
                step_data['feedback_tips']
            )
            
            # 사용자 응답 기록
            scenario_data['user_responses'].append({
                'step': current_step + 1,
                'user_message': user_message,
                'feedback': feedback,
                'timestamp': datetime.now().isoformat()
            })
            
            # 다음 단계로 진행
            scenario_data['current_step'] += 1
            next_step = scenario_data['current_step']
            
            if next_step < len(scenario['steps']):
                # 다음 단계가 있는 경우
                next_step_data = scenario['steps'][next_step]
                return {
                    "success": True,
                    "feedback": feedback,
                    "ai_message": next_step_data['ai_message'],
                    "expected_responses": next_step_data['expected_responses'],
                    "step": next_step + 1,
                    "total_steps": len(scenario['steps']),
                    "completed": False
                }
            else:
                # 시나리오 완료
                return {
                    "success": True,
                    "feedback": feedback,
                    "ai_message": "Great job! You've completed this scenario. Would you like to try another one?",
                    "completed": True,
                    "summary": self._generate_scenario_summary(scenario_data)
                }
        
        return {
            "success": False,
            "error": "시나리오가 이미 완료되었습니다."
        }
    
    def _analyze_user_response(
        self, 
        user_message: str, 
        expected_responses: List[str],
        feedback_tip: str
    ) -> Dict[str, Any]:
        """사용자 응답 분석 및 피드백 생성"""
        
        user_lower = user_message.lower().strip()
        
        # 정확도 계산 (단순한 키워드 매칭)
        accuracy_score = 0
        matched_keywords = []
        
        for expected in expected_responses:
            expected_words = expected.lower().split()
            for word in expected_words:
                if word in user_lower:
                    accuracy_score += 1
                    matched_keywords.append(word)
        
        # 피드백 생성
        if accuracy_score >= 2:
            feedback_level = "excellent"
            message = "Perfect! Your response was very natural."
        elif accuracy_score >= 1:
            feedback_level = "good"
            message = "Good response! Try to be more specific next time."
        else:
            feedback_level = "needs_improvement"
            message = f"Try this instead: {feedback_tip}"
        
        return {
            "level": feedback_level,
            "message": message,
            "accuracy_score": accuracy_score,
            "matched_keywords": matched_keywords,
            "suggestion": feedback_tip if feedback_level == "needs_improvement" else None
        }
    
    def _generate_scenario_summary(self, scenario_data: Dict) -> Dict[str, Any]:
        """시나리오 완료 후 요약 생성"""
        
        responses = scenario_data['user_responses']
        total_responses = len(responses)
        
        if total_responses == 0:
            return {"message": "No responses recorded"}
        
        # 전체 정확도 계산
        total_accuracy = sum(r['feedback']['accuracy_score'] for r in responses)
        average_accuracy = total_accuracy / total_responses
        
        # 레벨 분포
        level_counts = {}
        for response in responses:
            level = response['feedback']['level']
            level_counts[level] = level_counts.get(level, 0) + 1
        
        return {
            "total_responses": total_responses,
            "average_accuracy": round(average_accuracy, 2),
            "level_distribution": level_counts,
            "completed_at": datetime.now().isoformat(),
            "duration_minutes": 5  # 실제로는 계산해야 함
        }
    
    def _add_default_scenarios(self):
        """기본 시나리오 추가 (데이터 없을 때)"""
        
        self.conversation_scenarios = {
            'airport': {'scenarios': [], 'dialogues': [], 'common_phrases': []},
            'restaurant': {'scenarios': [], 'dialogues': [], 'common_phrases': []},
            'hotel': {'scenarios': [], 'dialogues': [], 'common_phrases': []},
            'street': {'scenarios': [], 'dialogues': [], 'common_phrases': []}
        }
    
    def _get_default_scenario(self, situation: str, difficulty: str) -> Dict:
        """기본 시나리오 반환"""
        
        return {
            'dialogue': f'Basic {situation} conversation scenario',
            'relevance_score': 1,
            'key_phrases': ['hello', 'please', 'thank you'],
            'difficulty': difficulty
        }
    
    def get_available_situations(self) -> List[str]:
        """사용 가능한 상황 목록"""
        return list(self.conversation_scenarios.keys())
    
    def get_session_status(self, session_id: str) -> Dict[str, Any]:
        """세션 상태 조회"""
        
        if session_id not in self.current_scenarios:
            return {"exists": False}
        
        scenario_data = self.current_scenarios[session_id]
        
        return {
            "exists": True,
            "situation": scenario_data['situation'],
            "current_step": scenario_data['current_step'] + 1,
            "total_steps": len(scenario_data['scenario']['steps']),
            "responses_count": len(scenario_data['user_responses']),
            "started_at": scenario_data['started_at']
        }

# 전역 인스턴스
conversation_ai_service = ScenarioConversationService()