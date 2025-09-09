# services/fine_tuning_manager.py
import json
import os
import asyncio
import logging
from typing import Dict, List, Optional
from datetime import datetime
import openai
from openai import AsyncOpenAI
from .conversation_data_collector import data_collector

logger = logging.getLogger(__name__)

class FineTuningManager:
    """Fine-tuning 관리 시스템"""
    
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            logger.warning("OPENAI_API_KEY가 설정되지 않았습니다.")
            self.client = None
        else:
            self.client = AsyncOpenAI(api_key=self.api_key)
        
        self.data_collector = data_collector
        self.min_data_threshold = 50  # 상황별 최소 데이터 수
        self.jobs_status = {}  # 진행 중인 작업 상태
    
    async def check_data_readiness(self, situation: str) -> Dict:
        """특정 상황의 데이터 준비 상태 확인"""
        
        try:
            stats = await self.data_collector.get_statistics()
            situation_data = stats.get('high_quality_by_situation', {}).get(situation, 0)
            
            return {
                "situation": situation,
                "available_data": situation_data,
                "required_minimum": self.min_data_threshold,
                "ready": situation_data >= self.min_data_threshold,
                "progress_percentage": min(100, (situation_data / self.min_data_threshold) * 100)
            }
            
        except Exception as e:
            logger.error(f"데이터 준비 상태 확인 오류: {e}")
            return {
                "situation": situation,
                "ready": False,
                "error": str(e)
            }
    
    async def prepare_fine_tuning_data(self, situation: str, min_satisfaction: float = 0.7) -> str:
        """Fine-tuning용 JSONL 데이터 준비"""
        
        if not self.client:
            raise ValueError("OpenAI API 키가 설정되지 않았습니다.")
        
        # 데이터 준비 상태 확인
        readiness = await self.check_data_readiness(situation)
        if not readiness["ready"]:
            raise ValueError(f"데이터 부족: {readiness['available_data']}개 (최소 {self.min_data_threshold}개 필요)")
        
        # 고품질 대화 데이터 추출
        conversations = await self.data_collector.get_training_data(
            situation=situation,
            min_satisfaction=min_satisfaction,
            min_turns=3,
            limit=1000
        )
        
        logger.info(f"Fine-tuning 데이터 준비: {situation} - {len(conversations)}개 대화")
        
        training_data = []
        
        for conv in conversations:
            try:
                # 시스템 프롬프트 생성
                system_prompt = self._generate_system_prompt(situation, conv['user_level'])
                
                # 훈련 데이터 형식으로 변환
                training_item = {
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": conv['user_message']},
                        {"role": "assistant", "content": conv['ai_response']}
                    ]
                }
                
                training_data.append(training_item)
                
            except Exception as e:
                logger.warning(f"대화 데이터 변환 오류: {e}")
                continue
        
        # JSONL 파일로 저장
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"fine_tuning_{situation}_{timestamp}.jsonl"
        
        with open(filename, 'w', encoding='utf-8') as f:
            for item in training_data:
                f.write(json.dumps(item, ensure_ascii=False) + '\n')
        
        logger.info(f"Fine-tuning 데이터 파일 생성: {filename} ({len(training_data)}개 항목)")
        return filename
    
    def _generate_system_prompt(self, situation: str, user_level: str) -> str:
        """상황과 레벨에 맞는 시스템 프롬프트"""
        
        base_prompts = {
            "airport": "You are a professional and helpful airport staff member assisting passengers with check-in, boarding, and travel-related questions.",
            "restaurant": "You are an experienced and friendly restaurant server helping customers with menu selection, ordering, and providing an excellent dining experience.",
            "hotel": "You are a courteous and knowledgeable hotel front desk clerk assisting guests with check-in, room service, and hotel amenities.",
            "street": "You are a helpful and friendly local resident providing directions, recommendations, and assistance to visitors in your city."
        }
        
        level_adjustments = {
            "beginner": "Use simple vocabulary and clear, short sentences. Speak slowly and repeat important information. Be very patient and encouraging.",
            "intermediate": "Use moderate complexity vocabulary and varied sentence structures. Provide helpful explanations when needed. Encourage natural conversation.",
            "advanced": "Use natural, fluent language with appropriate professional terminology. Engage in sophisticated conversation while maintaining your role."
        }
        
        situation_specific = {
            "airport": "Focus on check-in procedures, boarding information, baggage requirements, and travel documentation. Be efficient but thorough.",
            "restaurant": "Focus on menu recommendations, dietary restrictions, ordering process, and creating a pleasant dining atmosphere.",
            "hotel": "Focus on room assignments, hotel services, local recommendations, and ensuring guest satisfaction.",
            "street": "Focus on clear directions, local landmarks, transportation options, and helpful local knowledge."
        }
        
        return f"""{base_prompts.get(situation, '')}

LANGUAGE LEVEL: {level_adjustments.get(user_level, '')}

ROLE FOCUS: {situation_specific.get(situation, '')}

CONVERSATION GUIDELINES:
- Stay in character throughout the conversation
- Provide accurate and helpful information
- Be patient with language learners
- Gently correct mistakes when appropriate
- Ask relevant follow-up questions to continue the conversation
- Maintain a professional yet friendly tone"""
    
    async def start_fine_tuning(self, situation: str) -> Dict:
        """Fine-tuning 작업 시작"""
        
        if not self.client:
            return {
                "success": False,
                "error": "OpenAI API 키가 설정되지 않았습니다."
            }
        
        try:
            # 데이터 준비
            training_file_path = await self.prepare_fine_tuning_data(situation)
            
            # OpenAI에 파일 업로드
            logger.info(f"OpenAI에 훈련 파일 업로드 중: {training_file_path}")
            
            with open(training_file_path, 'rb') as f:
                training_file = await self.client.files.create(
                    file=f,
                    purpose='fine-tune'
                )
            
            # Fine-tuning 작업 생성
            logger.info(f"Fine-tuning 작업 생성 중: {situation}")
            
            fine_tuning_job = await self.client.fine_tuning.jobs.create(
                training_file=training_file.id,
                model="gpt-3.5-turbo",
                suffix=f"lang-learn-{situation}",
                hyperparameters={
                    "n_epochs": 3,  # 에포크 수
                    "batch_size": 1,  # 배치 크기
                    "learning_rate_multiplier": 0.1  # 학습률
                }
            )
            
            # 작업 상태 저장
            job_info = {
                "job_id": fine_tuning_job.id,
                "situation": situation,
                "status": fine_tuning_job.status,
                "created_at": datetime.now().isoformat(),
                "training_file": training_file.id,
                "training_file_path": training_file_path
            }
            
            self.jobs_status[fine_tuning_job.id] = job_info
            
            logger.info(f"Fine-tuning 작업 시작됨: {fine_tuning_job.id}")
            
            return {
                "success": True,
                "job_id": fine_tuning_job.id,
                "status": fine_tuning_job.status,
                "training_file": training_file.id,
                "model_name": f"gpt-3.5-turbo-{fine_tuning_job.id}",
                "situation": situation,
                "estimated_completion": "20-40 minutes"
            }
            
        except Exception as e:
            logger.error(f"Fine-tuning 시작 오류: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def check_fine_tuning_status(self, job_id: str) -> Dict:
        """Fine-tuning 상태 확인"""
        
        if not self.client:
            return {"error": "OpenAI API 키가 설정되지 않았습니다."}
        
        try:
            job = await self.client.fine_tuning.jobs.retrieve(job_id)
            
            # 로컬 상태 업데이트
            if job_id in self.jobs_status:
                self.jobs_status[job_id]["status"] = job.status
                if job.fine_tuned_model:
                    self.jobs_status[job_id]["fine_tuned_model"] = job.fine_tuned_model
            
            status_info = {
                "job_id": job_id,
                "status": job.status,
                "fine_tuned_model": job.fine_tuned_model,
                "created_at": job.created_at,
                "finished_at": job.finished_at,
                "training_file": job.training_file,
                "result_files": job.result_files,
                "hyperparameters": job.hyperparameters
            }
            
            # 로컬 정보 추가
            if job_id in self.jobs_status:
                local_info = self.jobs_status[job_id]
                status_info.update({
                    "situation": local_info.get("situation"),
                    "training_file_path": local_info.get("training_file_path")
                })
            
            return status_info
            
        except Exception as e:
            logger.error(f"Fine-tuning 상태 확인 오류: {e}")
            return {"error": str(e)}
    
    async def list_fine_tuning_jobs(self) -> List[Dict]:
        """모든 Fine-tuning 작업 목록"""
        
        if not self.client:
            return []
        
        try:
            jobs = await self.client.fine_tuning.jobs.list()
            
            job_list = []
            for job in jobs.data:
                job_info = {
                    "job_id": job.id,
                    "status": job.status,
                    "model": job.model,
                    "fine_tuned_model": job.fine_tuned_model,
                    "created_at": job.created_at,
                    "finished_at": job.finished_at
                }
                
                # 로컬 정보 추가
                if job.id in self.jobs_status:
                    local_info = self.jobs_status[job.id]
                    job_info["situation"] = local_info.get("situation")
                
                job_list.append(job_info)
            
            return job_list
            
        except Exception as e:
            logger.error(f"Fine-tuning 작업 목록 조회 오류: {e}")
            return []
    
    async def test_fine_tuned_model(self, model_name: str, situation: str, test_message: str) -> Dict:
        """Fine-tuned 모델 테스트"""
        
        if not self.client:
            return {"error": "OpenAI API 키가 설정되지 않았습니다."}
        
        try:
            system_prompt = self._generate_system_prompt(situation, "intermediate")
            
            response = await self.client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": test_message}
                ],
                max_tokens=200,
                temperature=0.7
            )
            
            return {
                "success": True,
                "model": model_name,
                "test_message": test_message,
                "response": response.choices[0].message.content,
                "tokens_used": response.usage.total_tokens
            }
            
        except Exception as e:
            logger.error(f"Fine-tuned 모델 테스트 오류: {e}")
            return {
                "success": False,
                "error": str(e)
            }

# 전역 인스턴스
fine_tuning_manager = FineTuningManager()