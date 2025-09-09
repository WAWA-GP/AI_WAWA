# services/conversation_data_collector.py
# 환경변수를 가장 먼저 로드
from dotenv import load_dotenv
load_dotenv()

import json
import asyncio
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import logging
from supabase import create_client, Client

logger = logging.getLogger(__name__)

class ConversationDataCollector:
    """대화 데이터 수집 및 저장 시스템 (Supabase 연동)"""
    
    def __init__(self):
        print("ConversationDataCollector 초기화 시작...")
        
        # Supabase 클라이언트 초기화
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_KEY")
        
        print(f"[DEBUG] SUPABASE_URL: {self.supabase_url}")
        print(f"[DEBUG] SUPABASE_KEY: {'설정됨' if self.supabase_key else '설정되지 않음'}")
        print(f"[DEBUG] SUPABASE_KEY 길이: {len(self.supabase_key) if self.supabase_key else 0}")
        
        if not self.supabase_url or not self.supabase_key:
            logger.error("❌ SUPABASE_URL 또는 SUPABASE_KEY가 설정되지 않았습니다.")
            logger.error(f"URL: {self.supabase_url}")
            logger.error(f"KEY: {'있음' if self.supabase_key else '없음'}")
            
            # .env 파일 존재 확인
            env_file_exists = os.path.exists('.env')
            env_file_exists_in_parent = os.path.exists('../.env')
            print(f"[DEBUG] .env 파일 존재 (현재 디렉토리): {env_file_exists}")
            print(f"[DEBUG] .env 파일 존재 (상위 디렉토리): {env_file_exists_in_parent}")
            print(f"[DEBUG] 현재 작업 디렉토리: {os.getcwd()}")
            
            self.supabase = None
            return
        
        try:
            print("Supabase 클라이언트 생성 시도...")
            self.supabase: Client = create_client(self.supabase_url, self.supabase_key)
            print("✅ Supabase 클라이언트 생성 성공!")
            logger.info("📊 Supabase 대화 데이터 수집기 초기화 완료")
            
            # 기본 연결 테스트
            try:
                # 간단한 테이블 조회로 연결 테스트
                test_response = self.supabase.table('conversation_turns').select('*').limit(1).execute()
                print("✅ Supabase 연결 테스트 성공")
            except Exception as test_error:
                print(f"⚠️ Supabase 연결 테스트 실패: {test_error}")
            
            
        except Exception as e:
            logger.error(f"❌ Supabase 초기화 오류: {e}")
            logger.error(f"오류 타입: {type(e).__name__}")
            print(f"[DEBUG] 상세 오류: {str(e)}")
            
            # 구체적인 오류 분석
            if "Invalid API key" in str(e):
                logger.error("API 키가 잘못되었습니다. Supabase 대시보드에서 확인하세요.")
            elif "Invalid URL" in str(e):
                logger.error("URL이 잘못되었습니다. 형식: https://xxxxx.supabase.co")
            elif "Connection" in str(e):
                logger.error("네트워크 연결을 확인하세요.")
            
            self.supabase = None

    async def start_session(self, session_id: str, user_id: str, situation: str, user_level: str, mode: str = "openai"):
        """새 세션 시작 기록"""
        
        if not self.supabase:
            logger.warning("Supabase가 초기화되지 않음")
            return
        
        try:
            session_data = {
                'session_id': session_id,
                'user_id': user_id,
                'situation': situation,
                'user_level': user_level,
                'mode': mode,
                'start_time': datetime.now().isoformat(),
                'total_turns': 0,
                'completion_status': 'active',
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            }
            
            response = self.supabase.table('session_metadata').upsert(session_data).execute()
            
            logger.debug(f"🎯 세션 시작 기록: {session_id}")
            
        except Exception as e:
            logger.error(f"세션 시작 기록 오류: {e}")
    
    async def log_conversation_turn(
        self,
        session_id: str,
        turn_index: int,
        situation: str,
        user_level: str,
        user_message: str,
        ai_response: str,
        response_mode: str = "openai",
        response_time_ms: float = None,
        context_data: Dict = None
    ):
        """대화 턴 로깅"""
        
        if not self.supabase:
            logger.warning("Supabase가 초기화되지 않음")
            return
        
        try:
            turn_data = {
                'session_id': session_id,
                'turn_index': turn_index,
                'situation': situation,
                'user_level': user_level,
                'user_message': user_message,
                'ai_response': ai_response,
                'response_mode': response_mode,
                'response_time_ms': response_time_ms,
                'context_data': json.dumps(context_data or {}),
                'created_at': datetime.now().isoformat()
            }
            
            # 대화 턴 삽입
            response = self.supabase.table('conversation_turns').insert(turn_data).execute()
            
            # 세션 메타데이터 업데이트 (턴 카운트 증가)
            update_response = self.supabase.table('session_metadata').update({
                'total_turns': turn_index + 1,
                'updated_at': datetime.now().isoformat()
            }).eq('session_id', session_id).execute()
            
            logger.debug(f"💬 대화 턴 로깅: {session_id}#{turn_index}")
            
        except Exception as e:
            logger.error(f"대화 턴 로깅 오류: {e}")
    
    async def update_user_feedback(
        self, 
        session_id: str, 
        turn_index: int, 
        satisfaction: float,
        feedback_comment: str = None
    ):
        """사용자 피드백 업데이트"""
        
        if not self.supabase:
            logger.warning("Supabase가 초기화되지 않음")
            return
        
        if not 0 <= satisfaction <= 1:
            logger.warning(f"잘못된 만족도 값: {satisfaction}")
            return
        
        try:
            # 해당 턴 업데이트
            update_data = {
                'user_satisfaction': satisfaction,
                'feedback_comment': feedback_comment,
                'updated_at': datetime.now().isoformat()
            }
            
            response = self.supabase.table('conversation_turns').update(update_data).eq(
                'session_id', session_id
            ).eq('turn_index', turn_index).execute()
            
            if response.data:
                # 세션 평균 만족도 업데이트
                await self._update_session_satisfaction(session_id)
                logger.debug(f"👍 피드백 업데이트: {session_id}#{turn_index} = {satisfaction}")
            else:
                logger.warning(f"피드백 업데이트 실패: {session_id}#{turn_index}")
                
        except Exception as e:
            logger.error(f"피드백 업데이트 오류: {e}")
    
    async def _update_session_satisfaction(self, session_id: str):
        """세션 평균 만족도 계산 및 업데이트"""
        
        try:
            # 해당 세션의 모든 만족도 조회
            response = self.supabase.table('conversation_turns').select(
                'user_satisfaction'
            ).eq('session_id', session_id).not_.is_('user_satisfaction', 'null').execute()
            
            if response.data:
                satisfactions = [float(row['user_satisfaction']) for row in response.data]
                average_satisfaction = sum(satisfactions) / len(satisfactions)
                
                # 세션 메타데이터 업데이트
                self.supabase.table('session_metadata').update({
                    'average_satisfaction': average_satisfaction,
                    'updated_at': datetime.now().isoformat()
                }).eq('session_id', session_id).execute()
                
        except Exception as e:
            logger.error(f"세션 만족도 업데이트 오류: {e}")
    
    async def end_session(self, session_id: str, completion_status: str = "completed"):
        """세션 종료 기록"""
        
        if not self.supabase:
            logger.warning("Supabase가 초기화되지 않음")
            return
        
        try:
            update_data = {
                'end_time': datetime.now().isoformat(),
                'completion_status': completion_status,
                'updated_at': datetime.now().isoformat()
            }
            
            response = self.supabase.table('session_metadata').update(update_data).eq(
                'session_id', session_id
            ).execute()
            
            logger.debug(f"🏁 세션 종료: {session_id} ({completion_status})")
            
        except Exception as e:
            logger.error(f"세션 종료 기록 오류: {e}")
    
    async def get_training_data(
        self, 
        situation: str = None, 
        min_satisfaction: float = 0.7,
        min_turns: int = 3,
        limit: int = 1000
    ) -> List[Dict]:
        """훈련용 고품질 데이터 추출"""
        
        if not self.supabase:
            logger.warning("Supabase가 초기화되지 않음")
            return []
        
        try:
            # 기본 쿼리 구성
            query = self.supabase.table('conversation_turns').select(
                '''
                session_id,
                situation,
                user_level,
                user_message,
                ai_response,
                user_satisfaction,
                context_data,
                session_metadata(total_turns, completion_status)
                '''
            ).gte('user_satisfaction', min_satisfaction)
            
            # 상황별 필터링
            if situation:
                query = query.eq('situation', situation)
            
            # 정렬 및 제한
            query = query.order('user_satisfaction', desc=True).order('created_at', desc=True)
            
            if limit:
                query = query.limit(limit)
            
            response = query.execute()
            
            # 결과 필터링 (최소 턴 수 조건)
            training_data = []
            for row in response.data:
                session_metadata = row.get('session_metadata')
                if session_metadata:
                    total_turns = session_metadata.get('total_turns', 0)
                    completion_status = session_metadata.get('completion_status', '')
                    
                    if total_turns >= min_turns and completion_status == 'completed':
                        context_data = {}
                        try:
                            context_str = row.get('context_data', '{}')
                            context_data = json.loads(context_str) if context_str else {}
                        except:
                            pass
                        
                        training_data.append({
                            'session_id': row['session_id'],
                            'situation': row['situation'],
                            'user_level': row['user_level'],
                            'user_message': row['user_message'],
                            'ai_response': row['ai_response'],
                            'satisfaction': row['user_satisfaction'],
                            'context': context_data
                        })
            
            logger.info(f"📚 훈련 데이터 추출: {len(training_data)}개 (상황: {situation or 'all'})")
            return training_data
            
        except Exception as e:
            logger.error(f"훈련 데이터 추출 오류: {e}")
            return []
    
    async def get_statistics(self) -> Dict:
        """수집된 데이터 통계"""
        
        if not self.supabase:
            logger.warning("Supabase가 초기화되지 않음")
            return {}
        
        try:
            stats = {}
            
            # 전체 턴 수
            response = self.supabase.table('conversation_turns').select('id', count='exact').execute()
            stats['total_turns'] = response.count
            
            # 전체 세션 수
            response = self.supabase.table('session_metadata').select('session_id', count='exact').execute()
            stats['total_sessions'] = response.count
            
            # 상황별 통계
            response = self.supabase.table('conversation_turns').select(
                'situation', count='exact'
            ).execute()
            
            situation_counts = {}
            for row in response.data:
                situation = row['situation']
                situation_counts[situation] = situation_counts.get(situation, 0) + 1
            stats['by_situation'] = situation_counts
            
            # 레벨별 통계
            response = self.supabase.table('conversation_turns').select(
                'user_level', count='exact'
            ).execute()
            
            level_counts = {}
            for row in response.data:
                level = row['user_level']
                level_counts[level] = level_counts.get(level, 0) + 1
            stats['by_level'] = level_counts
            
            # 평균 만족도
            response = self.supabase.table('conversation_turns').select(
                'user_satisfaction'
            ).not_.is_('user_satisfaction', 'null').execute()
            
            if response.data:
                satisfactions = [float(row['user_satisfaction']) for row in response.data]
                avg_satisfaction = sum(satisfactions) / len(satisfactions)
                stats['average_satisfaction'] = round(avg_satisfaction, 3)
            else:
                stats['average_satisfaction'] = None
            
            # 고품질 데이터 수
            response = self.supabase.table('conversation_turns').select(
                'id', count='exact'
            ).gte('user_satisfaction', 0.7).execute()
            stats['high_quality_turns'] = response.count
            
            # 상황별 고품질 데이터
            response = self.supabase.table('conversation_turns').select(
                'situation'
            ).gte('user_satisfaction', 0.7).execute()
            
            hq_situation_counts = {}
            for row in response.data:
                situation = row['situation']
                hq_situation_counts[situation] = hq_situation_counts.get(situation, 0) + 1
            stats['high_quality_by_situation'] = hq_situation_counts
            
            # Fine-tuning 준비 상태
            stats['fine_tuning_ready'] = {}
            for situation in ['airport', 'restaurant', 'hotel', 'street']:
                high_quality = hq_situation_counts.get(situation, 0)
                stats['fine_tuning_ready'][situation] = {
                    'count': high_quality,
                    'ready': high_quality >= 50  # 최소 50개 필요
                }
            
            return stats
            
        except Exception as e:
            logger.error(f"통계 조회 오류: {e}")
            return {}

# 전역 인스턴스
data_collector = ConversationDataCollector()