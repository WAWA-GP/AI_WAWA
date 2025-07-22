# app/services/conversation_ai_service.py
# OpenAI GPT-4와 기존 시나리오를 통합한 향상된 대화 서비스

import json
import random
import re
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

# OpenAI 서비스 임포트
try:
    from .openai_service import openai_service
except ImportError:
    openai_service = None
    logging.warning("OpenAI 서비스를 가져올 수 없습니다. 기본 시나리오만 사용됩니다.")

logger = logging.getLogger(__name__)

class EnhancedConversationService:
    """OpenAI GPT-4와 시나리오를 통합한 향상된 대화 서비스"""
    
    def __init__(self):
        self.conversation_scenarios = {}
        self.current_scenarios = {}  # session_id별 현재 시나리오
        self.openai_sessions = {}   # OpenAI 전용 세션들
        self.load_collected_data()
        
        # 대화 모드
        self.SCENARIO_MODE = "scenario"    # 기존 시나리오 기반
        self.OPENAI_MODE = "openai"       # OpenAI GPT-4 기반
        self.HYBRID_MODE = "hybrid"       # 혼합 모드
        
    def load_collected_data(self):
        """수집된 대화 데이터를 시나리오로 변환"""
        
        try:
            # 수집한 JSON 파일 읽기 (여러 경로 시도)
            json_filename = 'free_travel_conversations_en_20250722_161841.json'
            possible_paths = [
                json_filename,  # 현재 폴더
                f'../{json_filename}',  # 상위 폴더
                f'../../{json_filename}',  # 2단계 상위 폴더
            ]
            
            data = None
            for json_path in possible_paths:
                try:
                    with open(json_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        logger.info(f"JSON 파일 로드 성공: {json_path}")
                        break
                except FileNotFoundError:
                    continue
            
            if data is None:
                raise FileNotFoundError(f"JSON 파일을 찾을 수 없습니다: {json_filename}")
            
            logger.info(f"JSON 파일 구조: {list(data.keys())}")
            
            # JSON 구조 확인 및 대화 데이터 추출
            conversations = []
            if 'conversations' in data:
                conversations = data['conversations']
            elif isinstance(data, list):
                conversations = data
            else:
                # 다른 구조일 경우 키 확인
                for key in data.keys():
                    if isinstance(data[key], list):
                        conversations = data[key]
                        break
            
            logger.info(f"추출된 대화 수: {len(conversations)}")
            
            # 상황별로 대화 시나리오 분류
            for i, conversation in enumerate(conversations):
                try:
                    # 상황 추출 (다양한 키 이름 대응)
                    situation = None
                    for key in ['situation', 'context', 'scenario', 'scene', 'setting']:
                        if key in conversation:
                            situation = conversation[key].lower()
                            break
                    
                    if not situation:
                        # 대화 내용에서 상황 추정
                        dialogue_text = str(conversation.get('dialogue', ''))
                        situation = self._infer_situation_from_text(dialogue_text)
                    
                    if situation not in self.conversation_scenarios:
                        self.conversation_scenarios[situation] = {
                            'dialogues': [],
                            'common_phrases': [],
                            'scenarios': []
                        }
                    
                    # 실제 대화를 시나리오로 변환
                    dialogue_text = conversation.get('dialogue', '') or conversation.get('text', '') or str(conversation)
                    scenario = self._extract_scenario_from_dialogue(dialogue_text, situation)
                    
                    if scenario:
                        self.conversation_scenarios[situation]['scenarios'].append(scenario)
                        logger.debug(f"시나리오 추가: {situation} - {len(scenario.get('key_phrases', []))}개 핵심 표현")
                    
                except Exception as e:
                    logger.warning(f"대화 {i} 처리 중 오류: {e}")
                    continue
            
            # 기본 시나리오 추가 (데이터 없을 때 대비)
            self._add_default_scenarios()
            
            # 결과 로깅
            for situation, data in self.conversation_scenarios.items():
                scenario_count = len(data['scenarios'])
                logger.info(f"✅ {situation}: {scenario_count}개 시나리오 로드됨")
            
        except FileNotFoundError:
            logger.warning("수집된 대화 파일을 찾을 수 없음. 기본 시나리오만 사용")
            self._add_default_scenarios()
        except Exception as e:
            logger.error(f"데이터 로드 오류: {e}")
            self._add_default_scenarios()
    
    async def start_conversation(
        self,
        session_id: str,
        situation: str,
        difficulty: str = "beginner",
        language: str = "en",
        mode: str = "auto"  # "scenario", "openai", "hybrid", "auto"
    ) -> Dict[str, Any]:
        """새로운 대화 세션 시작 (모드 자동 선택 또는 지정)"""
        
        if situation not in self.conversation_scenarios:
            return {
                "success": False,
                "error": f"지원하지 않는 상황: {situation}"
            }
        
        try:
            # 모드 자동 선택
            if mode == "auto":
                # OpenAI 사용 가능하면 hybrid, 아니면 scenario
                mode = "hybrid" if openai_service and openai_service.client else "scenario"
            
            # 세션 설정
            session_config = {
                'situation': situation,
                'difficulty': difficulty,
                'language': language,
                'mode': mode,
                'started_at': datetime.now().isoformat(),
                'turn_count': 0
            }
            
            if mode == "openai" and openai_service:
                # OpenAI 전용 모드
                self.openai_sessions[session_id] = session_config
                
                # GPT-4로 시작 메시지 생성
                intro_message = await openai_service.generate_scenario_intro(
                    situation=situation,
                    language=language,
                    difficulty=difficulty
                )
                
                return {
                    "success": True,
                    "mode": mode,
                    "session_id": session_id,
                    "first_message": intro_message,
                    "scenario_title": f"AI-Powered {situation.title()} Conversation",
                    "features": ["intelligent_responses", "contextual_feedback", "adaptive_difficulty"]
                }
                
            elif mode == "hybrid" and openai_service:
                # 하이브리드 모드: OpenAI + 시나리오 데이터 활용
                self.openai_sessions[session_id] = session_config
                
                # 시나리오 데이터에서 상황별 컨텍스트 추출
                scenario_context = self._get_scenario_context(situation)
                
                # GPT-4로 컨텍스트를 반영한 시작 메시지 생성
                intro_message = await openai_service.generate_scenario_intro(
                    situation=situation,
                    language=language,
                    difficulty=difficulty
                )
                
                return {
                    "success": True,
                    "mode": mode,
                    "session_id": session_id,
                    "first_message": intro_message,
                    "scenario_title": f"Enhanced {situation.title()} Conversation",
                    "scenario_context": scenario_context,
                    "features": ["intelligent_responses", "scenario_based", "contextual_feedback"]
                }
                
            else:
                # 시나리오 모드 (기본)
                return await self._start_scenario_mode(session_id, situation, difficulty, language)
                
        except Exception as e:
            logger.error(f"대화 시작 오류: {e}")
            return {
                "success": False,
                "error": f"대화 시작 중 오류: {str(e)}"
            }
    
    async def process_user_response(
        self,
        session_id: str,
        user_message: str
    ) -> Dict[str, Any]:
        """사용자 메시지 처리 (모드에 따라 분기)"""
        
        # OpenAI 세션인지 확인
        if session_id in self.openai_sessions:
            return await self._process_openai_message(session_id, user_message)
        
        # 시나리오 세션인지 확인
        elif session_id in self.current_scenarios:
            return await self._process_scenario_message(session_id, user_message)
        
        else:
            return {
                "success": False,
                "error": "활성 세션이 없습니다. 먼저 대화를 시작해주세요."
            }
    
    async def _process_openai_message(
        self,
        session_id: str,
        user_message: str
    ) -> Dict[str, Any]:
        """OpenAI 모드 메시지 처리"""
        
        try:
            session_config = self.openai_sessions[session_id]
            
            # GPT-4로 응답 생성
            ai_result = await openai_service.generate_ai_response(
                session_id=session_id,
                user_message=user_message,
                situation=session_config['situation'],
                language=session_config['language'],
                difficulty=session_config['difficulty']
            )
            
            if ai_result["success"]:
                # 턴 카운트 증가
                session_config['turn_count'] += 1
                
                return {
                    "success": True,
                    "mode": session_config['mode'],
                    "ai_message": ai_result["ai_message"],
                    "feedback": ai_result["feedback"],
                    "turn_count": session_config['turn_count'],
                    "tokens_used": ai_result.get("tokens_used", 0),
                    "model": ai_result.get("model", "gpt-4"),
                    "completed": False  # OpenAI 모드는 무한 대화
                }
            else:
                # OpenAI 실패시 폴백
                if ai_result.get("fallback"):
                    logger.warning(f"OpenAI 실패, 시나리오 모드로 폴백: {session_id}")
                    return await self._fallback_to_scenario(session_id, user_message)
                else:
                    return ai_result
                    
        except Exception as e:
            logger.error(f"OpenAI 메시지 처리 오류: {e}")
            return {
                "success": False,
                "error": f"메시지 처리 중 오류: {str(e)}"
            }
    
    async def _process_scenario_message(
        self,
        session_id: str,
        user_message: str
    ) -> Dict[str, Any]:
        """시나리오 모드 메시지 처리 (기존 로직)"""
        
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
                    "mode": self.SCENARIO_MODE,
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
                    "mode": self.SCENARIO_MODE,
                    "feedback": feedback,
                    "ai_message": "Great job! You've completed this scenario. Would you like to try another one?",
                    "completed": True,
                    "summary": self._generate_scenario_summary(scenario_data)
                }
        
        return {
            "success": False,
            "error": "시나리오가 이미 완료되었습니다."
        }
    
    async def _fallback_to_scenario(
        self,
        session_id: str,
        user_message: str
    ) -> Dict[str, Any]:
        """OpenAI 실패시 시나리오 모드로 폴백"""
        
        try:
            session_config = self.openai_sessions[session_id]
            
            # 시나리오 모드로 전환
            scenario_session_id = f"{session_id}_fallback"
            
            # 시나리오 시작
            result = await self._start_scenario_mode(
                session_id=scenario_session_id,
                situation=session_config['situation'],
                difficulty=session_config['difficulty'],
                language=session_config['language']
            )
            
            if result["success"]:
                # 원래 세션 정리
                del self.openai_sessions[session_id]
                
                return {
                    "success": True,
                    "mode": "fallback_scenario",
                    "ai_message": result["first_message"],
                    "message": "시나리오 모드로 전환되었습니다.",
                    "new_session_id": scenario_session_id
                }
            else:
                return result
                
        except Exception as e:
            logger.error(f"폴백 처리 오류: {e}")
            return {
                "success": False,
                "error": "폴백 처리 중 오류가 발생했습니다."
            }
    
    async def _start_scenario_mode(
        self,
        session_id: str,
        situation: str,
        difficulty: str,
        language: str
    ) -> Dict[str, Any]:
        """기존 시나리오 모드로 대화 시작"""
        
        # 난이도에 맞는 시나리오 선택
        scenarios = self.conversation_scenarios[situation]['scenarios']
        
        if not scenarios:
            scenario = self._get_default_scenario(situation, difficulty)
        else:
            scenario = random.choice(scenarios)
        
        # 시나리오 구조화
        structured_scenario = self._create_scenario_structure(scenario, situation, difficulty)
        
        # 세션에 저장
        self.current_scenarios[session_id] = {
            'situation': situation,
            'difficulty': difficulty,
            'language': language,
            'mode': self.SCENARIO_MODE,
            'scenario': structured_scenario,
            'current_step': 0,
            'user_responses': [],
            'started_at': datetime.now().isoformat()
        }
        
        return {
            "success": True,
            "mode": self.SCENARIO_MODE,
            "session_id": session_id,
            "scenario_title": structured_scenario['title'],
            "first_message": structured_scenario['steps'][0]['ai_message'],
            "expected_responses": structured_scenario['steps'][0]['expected_responses']
        }
    
    def start_scenario(
        self,
        session_id: str,
        situation: str,
        difficulty: str = "beginner"
    ) -> Dict[str, Any]:
        """기존 API 호환성을 위한 동기 버전"""
        
        # 비동기 버전을 동기로 래핑
        import asyncio
        
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(
            self.start_conversation(session_id, situation, difficulty, "en", "auto")
        )
    
    def _get_scenario_context(self, situation: str) -> Dict[str, Any]:
        """상황별 시나리오 컨텍스트 추출"""
        
        scenarios = self.conversation_scenarios.get(situation, {}).get('scenarios', [])
        
        if not scenarios:
            return {"phrases": [], "topics": [], "scenario_count": 0}
        
        # 핵심 표현 수집
        all_phrases = []
        for scenario in scenarios[:10]:  # 최대 10개 시나리오에서 추출
            phrases = scenario.get('key_phrases', [])
            all_phrases.extend(phrases)
        
        # 중복 제거 및 상위 표현 선택
        unique_phrases = list(set(all_phrases))[:15]
        
        # 주요 주제 추출
        topics = [f"{situation} conversation", f"{situation} vocabulary", f"{situation} situations"]
        
        return {
            "phrases": unique_phrases,
            "topics": topics,
            "scenario_count": len(scenarios)
        }
    
    def _infer_situation_from_text(self, text: str) -> str:
        """텍스트에서 상황 추정"""
        text_lower = text.lower()
        
        if any(word in text_lower for word in ['airport', 'flight', 'boarding', 'check-in', 'gate', 'passport']):
            return 'airport'
        elif any(word in text_lower for word in ['restaurant', 'menu', 'order', 'table', 'waiter', 'food']):
            return 'restaurant'
        elif any(word in text_lower for word in ['hotel', 'room', 'reception', 'key', 'lobby', 'booking']):
            return 'hotel'
        elif any(word in text_lower for word in ['street', 'direction', 'way', 'map', 'lost', 'bus', 'subway']):
            return 'street'
        else:
            return 'general'
    
    def _extract_scenario_from_dialogue(self, dialogue_text: str, situation: str) -> Optional[Dict]:
        """실제 대화에서 시나리오 패턴 추출"""
        
        if not dialogue_text or len(dialogue_text.strip()) < 10:
            return None
        
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
        
        # 최소 관련도 기준 완화
        if relevance_score >= 0:  # 0 이상이면 포함
            return {
                'dialogue': dialogue_text[:500],  # 처음 500자만
                'relevance_score': max(relevance_score, 1),  # 최소 1점
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
    
    def _create_scenario_structure(self, base_scenario: Dict, situation: str, difficulty: str) -> Dict:
        """시나리오를 구조화된 대화 단계로 변환"""
        
        scenario_templates = {
            'airport': {
                'title': 'Airport Check-in',
                'steps': [
                    {
                        'step': 1,
                        'ai_message': 'Good morning! Welcome to the airport. How can I help you today?',
                        'expected_responses': ['check in', 'flight', 'need help', 'boarding pass'],
                        'feedback_tips': 'Try saying: "I need to check in for my flight"'
                    },
                    {
                        'step': 2,
                        'ai_message': 'May I see your passport and boarding pass?',
                        'expected_responses': ['here', 'sure', 'course', 'you are'],
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
                        'expected_responses': ['reservation', 'table', 'yes', 'under'],
                        'feedback_tips': 'You can say: "Yes, under [your name]" or "Table for [number] please"'
                    },
                    {
                        'step': 2,
                        'ai_message': 'Right this way. Here are your menus. Can I get you something to drink?',
                        'expected_responses': ['water', 'wine', 'coffee', 'drink'],
                        'feedback_tips': 'Simple responses work: "Water please" or "Coffee, please"'
                    }
                ]
            },
            'hotel': {
                'title': 'Hotel Check-in',
                'steps': [
                    {
                        'step': 1,
                        'ai_message': 'Good afternoon! Welcome to our hotel. How can I help you?',
                        'expected_responses': ['check in', 'reservation', 'room', 'booking'],
                        'feedback_tips': 'Try saying: "I have a reservation" or "I\'d like to check in"'
                    },
                    {
                        'step': 2,
                        'ai_message': 'May I have your name and ID please?',
                        'expected_responses': ['here', 'sure', 'name is', 'id'],
                        'feedback_tips': 'You can say: "Sure, here you are" or "My name is..."'
                    }
                ]
            },
            'street': {
                'title': 'Asking for Directions',
                'steps': [
                    {
                        'step': 1,
                        'ai_message': 'You look lost. Can I help you find something?',
                        'expected_responses': ['yes', 'help', 'looking for', 'where'],
                        'feedback_tips': 'Try saying: "Yes, I\'m looking for..." or "Can you help me find..."'
                    },
                    {
                        'step': 2,
                        'ai_message': 'Go straight ahead for two blocks, then turn left.',
                        'expected_responses': ['thank you', 'thanks', 'got it', 'understand'],
                        'feedback_tips': 'A polite response: "Thank you very much" or "I understand"'
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
                    'expected_responses': ['hello', 'hi', 'good'],
                    'feedback_tips': 'Try greeting back politely'
                }
            ]
        })
        
        return template
    
    def _analyze_user_response(
        self, 
        user_message: str, 
        expected_responses: List[str],
        feedback_tip: str
    ) -> Dict[str, Any]:
        """사용자 응답 분석 및 피드백 생성 - 개선된 버전"""
        
        user_lower = user_message.lower().strip()
        
        # 정확도 계산 (개선된 키워드 매칭)
        accuracy_score = 0
        matched_keywords = []
        
        # 각 기대 응답과 사용자 입력 비교
        for expected in expected_responses:
            expected_words = expected.lower().split()
            for word in expected_words:
                if len(word) > 2 and word in user_lower:  # 3글자 이상의 의미있는 단어만
                    accuracy_score += 1
                    matched_keywords.append(word)
        
        # 부분 매칭도 고려 (더 유연한 평가)
        partial_matches = 0
        for expected in expected_responses:
            if any(part in user_lower for part in expected.lower().split() if len(part) > 2):
                partial_matches += 1
        
        # 최종 점수 계산
        total_score = accuracy_score + (partial_matches * 0.5)
        
        # 피드백 생성 (기준 완화)
        if total_score >= 1.5 or len(matched_keywords) >= 2:
            feedback_level = "excellent"
            message = "Perfect! Your response was very natural."
        elif total_score >= 0.5 or len(matched_keywords) >= 1:
            feedback_level = "good"
            message = "Good response! Try to be more specific next time."
        else:
            feedback_level = "needs_improvement"
            message = f"Try this instead: {feedback_tip}"
        
        return {
            "level": feedback_level,
            "message": message,
            "accuracy_score": total_score,
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
        
        # 기존 데이터 유지하면서 기본값 추가
        default_situations = ['airport', 'restaurant', 'hotel', 'street']
        
        for situation in default_situations:
            if situation not in self.conversation_scenarios:
                self.conversation_scenarios[situation] = {
                    'scenarios': [], 
                    'dialogues': [], 
                    'common_phrases': []
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
        
        # OpenAI 세션 확인
        if session_id in self.openai_sessions:
            session_config = self.openai_sessions[session_id]
            if openai_service:
                conversation_summary = openai_service.get_conversation_summary(session_id)
            else:
                conversation_summary = {"conversation_length": 0}
            
            return {
                "exists": True,
                "mode": session_config['mode'],
                "situation": session_config['situation'],
                "difficulty": session_config['difficulty'],
                "language": session_config['language'],
                "turn_count": session_config['turn_count'],
                "conversation_length": conversation_summary['conversation_length'],
                "started_at": session_config['started_at']
            }
        
        # 시나리오 세션 확인
        elif session_id in self.current_scenarios:
            scenario_data = self.current_scenarios[session_id]
            
            return {
                "exists": True,
                "mode": scenario_data.get('mode', self.SCENARIO_MODE),
                "situation": scenario_data['situation'],
                "difficulty": scenario_data['difficulty'],
                "language": scenario_data.get('language', 'en'),
                "current_step": scenario_data['current_step'] + 1,
                "total_steps": len(scenario_data['scenario']['steps']),
                "responses_count": len(scenario_data['user_responses']),
                "started_at": scenario_data['started_at']
            }
        
        else:
            return {"exists": False}
    
    async def end_conversation(self, session_id: str) -> Dict[str, Any]:
        """대화 세션 종료"""
        
        try:
            summary = None
            
            # OpenAI 세션 종료
            if session_id in self.openai_sessions:
                if openai_service:
                    summary = openai_service.get_conversation_summary(session_id)
                    openai_service.clear_conversation_history(session_id)
                del self.openai_sessions[session_id]
            
            # 시나리오 세션 종료
            elif session_id in self.current_scenarios:
                scenario_data = self.current_scenarios[session_id]
                summary = self._generate_scenario_summary(scenario_data)
                del self.current_scenarios[session_id]
            
            return {
                "success": True,
                "message": "대화 세션이 종료되었습니다.",
                "summary": summary,
                "ended_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"세션 종료 오류: {e}")
            return {
                "success": False,
                "error": f"세션 종료 중 오류: {str(e)}"
            }
    
    async def get_openai_status(self) -> Dict[str, Any]:
        """OpenAI 서비스 상태 확인"""
        
        if openai_service:
            return await openai_service.test_connection()
        else:
            return {
                "connected": False,
                "error": "OpenAI 서비스가 사용할 수 없습니다"
            }

# 전역 인스턴스
enhanced_conversation_service = EnhancedConversationService()
conversation_ai_service = enhanced_conversation_service  # 호환성을 위한 별칭