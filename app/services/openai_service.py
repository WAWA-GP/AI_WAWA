# services/openai_service.py
# OpenAI GPT-4 연동 서비스

import asyncio
import json
import logging
import os
from typing import Dict, List, Optional, Any
from datetime import datetime
import openai
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class OpenAIService:
    """OpenAI GPT-4 연동 서비스"""

    def __init__(self):
        # API 키 설정
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            logger.warning(
                "OPENAI_API_KEY가 설정되지 않았습니다. 기본 시나리오만 사용됩니다."
            )
            self.client = None
        else:
            # 비동기 클라이언트 초기화
            self.client = AsyncOpenAI(api_key=self.api_key)
            logger.info("OpenAI GPT-4 클라이언트 초기화 완료")

        # 대화 히스토리 관리 (세션별)
        self.conversation_histories = {}

        # 언어별 시스템 프롬프트
        self.system_prompts = self._load_system_prompts()

        # 설정값
        self.max_tokens = 500
        self.temperature = 0.7
        self.max_history_length = 20  # 최대 대화 히스토리 길이

    def _load_system_prompts(self) -> Dict[str, Dict[str, str]]:
        """언어별, 상황별 시스템 프롬프트 로드 - 5개 언어 지원"""

        return {
            "ko": {
                "airport": """당신은 친근하고 전문적인 인천공항 직원입니다. 
사용자는 한국어를 배우는 외국인 여행자입니다:
1. 간단하고 명확한 한국어를 사용하세요
2. 사용자의 한국어 실수를 자연스럽게 교정해주세요
3. 공항 체크인, 보안검색, 탑승 등 상황에 맞는 대화를 진행하세요
4. 사용자가 어려워하면 영어로 도움말을 제공하세요
5. 긍정적이고 격려하는 톤을 유지하세요
6. 한국 문화와 예의에 대해서도 알려주세요""",
                "restaurant": """당신은 친절한 한국 레스토랑 웨이터입니다.
사용자는 한국어를 배우는 외국인 손님입니다:
1. 메뉴 설명, 주문 받기, 서빙 등의 상황을 자연스럽게 연출하세요
2. 한국 음식에 대한 간단한 설명도 포함하세요
3. 사용자의 한국어 실력에 맞춰 대화 난이도를 조절하세요
4. 한국 식당 문화와 예의를 가르쳐주세요
5. 천천히 말하고 이해하기 쉽게 설명해주세요""",
                "hotel": """당신은 한국 호텔 프론트 데스크 직원입니다.
사용자는 한국어를 배우는 외국인 투숙객입니다:
1. 체크인, 체크아웃, 룸서비스 등 호텔 상황을 연출하세요
2. 정중하고 전문적인 한국어를 사용하세요
3. 호텔 시설과 서비스에 대한 정보를 제공하세요
4. 한국 호텔 문화와 서비스를 친절히 설명해주세요
5. 외국인 고객의 어려움을 이해하고 도움을 주세요""",
                "street": """당신은 친절한 한국인 시민입니다.
사용자는 한국어를 배우는 외국인 여행자입니다:
1. 길 찾기, 교통수단, 일상 대화를 도와주세요
2. 한국의 문화와 예의에 대해서도 알려주세요
3. 현지인처럼 자연스럽고 친근한 말투를 사용하세요
4. 한국 생활에 도움이 되는 실용적인 팁을 제공하세요
5. 사용자가 한국어 실수를 해도 이해하고 도움을 주세요""",
            },
            "en": {
                "airport": """You are a friendly and professional airport staff member.
Since the user is learning English:
1. Use clear and simple English
2. Naturally correct grammar mistakes in a supportive way
3. Handle airport situations like check-in, security, boarding
4. Provide helpful vocabulary related to air travel
5. Maintain an encouraging and positive tone""",
                "restaurant": """You are a friendly restaurant server.
Since the user is learning English:
1. Create natural restaurant scenarios: seating, ordering, serving
2. Describe menu items and help with food vocabulary
3. Use polite restaurant English and teach dining etiquette""",
                "hotel": """You are a professional hotel front desk clerk.
Since the user is learning English:
1. Handle hotel situations: check-in, check-out, room service
2. Use formal but friendly hospitality English
3. Provide information about hotel facilities and services""",
                "street": """You are a helpful local resident.
Since the user is learning English:
1. Help with directions, transportation, and daily conversations
2. Use natural, conversational English
3. Share local knowledge and cultural tips""",
            },
            "ja": {
                "airport": """あなたは親切で専門的な空港スタッフです。
ユーザーが日本語を学んでいる外国人なので:
1. 簡潔で分かりやすい日本語を使ってください
2. 文法の間違いを自然に訂正してください
3. チェックイン、セキュリティ、搭乗などの空港業務を行ってください
4. 航空旅行に関する語彙を教えてください
5. 励ましの気持ちを込めて対応してください""",
                "restaurant": """あなたは親切なレストランのウェイターです。
ユーザーが日本語を学んでいる外国人なので:
1. 注文、接客、配膳などのレストランシーンを演出してください
2. メニューの説明と食事の語彙を教えてください
3. 丁寧なレストラン日本語とマナーを教えてください""",
                "hotel": """あなたは礼儀正しいホテルのフロントスタッフです。
ユーザーが日本語を学んでいる外国人なので:
1. チェックイン、チェックアウト、ルームサービスなどを対応してください
2. 丁寧で専門的な日本語を使ってください
3. ホテルの施設とサービスについて説明してください""",
                "street": """あなたは親切な地元の住民です。
ユーザーが日本語を学んでいる外国人なので:
1. 道案内、交通、日常会話を手伝ってください
2. 自然で親しみやすい日本語を使ってください
3. 地元の知識と文化的なヒントを共有してください""",
            },
            "zh": {
                "airport": """您是一位友善专业的机场工作人员。
用户正在学习中文，因此：
1. 使用清楚简单的中文
2. 自然地纠正语法错误
3. 处理值机、安检、登机等机场情况
4. 提供航空旅行相关词汇
5. 保持鼓励和积极的语调""",
                "restaurant": """您是一位友善的餐厅服务员。
用户正在学习中文，因此：
1. 创造自然的餐厅场景：就座、点餐、用餐
2. 描述菜单项目，帮助学习食物词汇
3. 使用礼貌的餐厅中文，教授用餐礼仪""",
                "hotel": """您是一位专业的酒店前台工作人员。
用户正在学习中文，因此：
1. 处理酒店情况：入住、退房、客房服务
2. 使用正式但友好的酒店中文
3. 提供酒店设施和服务信息""",
                "street": """您是一位乐于助人的当地居民。
用户正在学习中文，因此：
1. 帮助问路、交通和日常对话
2. 使用自然的对话中文
3. 分享当地知识和文化提示""",
            },
            "fr": {
                "airport": """Vous êtes un employé d'aéroport amical et professionnel.
L'utilisateur apprend le français, donc :
1. Utilisez un français clair et simple
2. Corrigez naturellement les erreurs de grammaire de manière bienveillante
3. Gérez les situations d'aéroport comme l'enregistrement, la sécurité, l'embarquement
4. Fournissez du vocabulaire utile lié aux voyages aériens
5. Maintenez un ton encourageant et positif""",
                "restaurant": """Vous êtes un serveur de restaurant amical.
L'utilisateur apprend le français, donc :
1. Créez des scénarios naturels de restaurant : placement, commande, service
2. Décrivez les éléments du menu et aidez avec le vocabulaire alimentaire
3. Utilisez un français poli de restaurant et enseignez l'étiquette""",
                "hotel": """Vous êtes un réceptionniste d'hôtel professionnel.
L'utilisateur apprend le français, donc :
1. Gérez les situations d'hôtel : check-in, check-out, service en chambre
2. Utilisez un français d'hospitalité formel mais amical
3. Fournissez des informations sur les installations et services de l'hôtel""",
                "street": """Vous êtes un résident local serviable.
L'utilisateur apprend le français, donc :
1. Aidez avec les directions, les transports et les conversations quotidiennes
2. Utilisez un français conversationnel naturel
3. Partagez des connaissances locales et des conseils culturels""",
            },
        }

    async def generate_ai_response(
        self,
        session_id: str,
        user_message: str,
        situation: str,
        language: str = "en",
        difficulty: str = "beginner",
        context: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """GPT-4를 사용한 AI 응답 생성"""

        if not self.client:
            return {
                "success": False,
                "error": "OpenAI API 키가 설정되지 않았습니다.",
                "fallback": True,
            }

        try:
            # 시스템 프롬프트 선택
            system_prompt = self._get_system_prompt(situation, language, difficulty)

            # 대화 히스토리 관리
            conversation = self._get_conversation_history(session_id)

            # 메시지 구성
            messages = [{"role": "system", "content": system_prompt}]

            # 기존 대화 히스토리 추가
            messages.extend(conversation)

            # 현재 사용자 메시지 추가
            messages.append({"role": "user", "content": user_message})

            # GPT-4 호출
            logger.info(f"GPT-4 요청: {session_id} - {user_message[:50]}...")

            response = await self.client.chat.completions.create(
                model="gpt-4",
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                stream=False,
            )

            ai_message = response.choices[0].message.content

            # 대화 히스토리 업데이트
            self._update_conversation_history(session_id, user_message, ai_message)

            # 응답 분석 및 피드백 생성
            feedback = await self._analyze_user_input(
                user_message, ai_message, language, difficulty
            )

            logger.info(f"GPT-4 응답 생성 성공: {session_id}")

            return {
                "success": True,
                "ai_message": ai_message,
                "feedback": feedback,
                "tokens_used": response.usage.total_tokens,
                "model": "gpt-4",
            }

        except Exception as e:
            logger.error(f"GPT-4 요청 오류: {e}")
            return {
                "success": False,
                "error": f"AI 응답 생성 중 오류: {str(e)}",
                "fallback": True,
            }

    def _get_system_prompt(self, situation: str, language: str, difficulty: str) -> str:
        """상황과 언어, 그리고 원하는 출력 형식에 맞는 시스템 프롬프트를 생성합니다."""

        # 1. 기존과 동일하게 기본 역할 프롬프트를 가져옵니다.
        base_prompt = self.system_prompts.get(language, self.system_prompts["en"])
        situation_prompt = base_prompt.get(situation, base_prompt.get("airport", ""))

        # 2. ❗️ [핵심 수정] 출력 형식을 매우 구체적으로 지시하는 'format_instructions'를 추가합니다.
        # f-string을 사용하여 사용자의 난이도(difficulty)를 프롬프트에 동적으로 포함시킵니다.
        format_instructions = f"""

You MUST strictly follow this response format every time:

1.  **Conversational Reply:** [First, provide your natural, in-character conversational reply here.]
2.  **Separator:** After the reply, add a blank line, then the separator line, then another blank line. The separator line should be: =======================
3.  **Educational Content:** Below the separator, provide 1-2 useful phrases or vocabulary words from your reply. The explanations should be simple and suitable for a '{difficulty}' level learner.

— EXAMPLE OUTPUT —
Of course, I can help with that. Your gate is B52, located in the next concourse.

=======================

* **Concourse**: A large open area inside an airport terminal where people wait for their planes.
* **Located in**: A common and simple way to say where something is.
"""

        # 3. 역할 프롬프트와 형식 프롬프트를 합쳐서 최종 지시문을 완성합니다.
        return situation_prompt + format_instructions

    def _get_conversation_history(self, session_id: str) -> List[Dict[str, str]]:
        """세션별 대화 히스토리 조회"""

        if session_id not in self.conversation_histories:
            self.conversation_histories[session_id] = []

        return self.conversation_histories[session_id]

    def _update_conversation_history(
        self, session_id: str, user_message: str, ai_message: str
    ):
        """대화 히스토리 업데이트"""

        if session_id not in self.conversation_histories:
            self.conversation_histories[session_id] = []

        history = self.conversation_histories[session_id]

        # 새 대화 추가
        history.append({"role": "user", "content": user_message})
        history.append({"role": "assistant", "content": ai_message})

        # 히스토리 길이 제한
        if len(history) > self.max_history_length:
            # 오래된 대화 제거 (시스템 메시지는 보존)
            self.conversation_histories[session_id] = history[
                -self.max_history_length :
            ]

        logger.debug(f"대화 히스토리 업데이트: {session_id} - {len(history)}개 메시지")

    async def _analyze_user_input(
        self, user_message: str, ai_message: str, language: str, difficulty: str
    ) -> Dict[str, Any]:
        """사용자 입력 분석 및 피드백 생성"""

        if not self.client:
            return {
                "level": "good",
                "message": "좋은 응답입니다!",
                "grammar_feedback": [],
                "vocabulary_suggestions": [],
                "pronunciation_tips": [],
            }

        try:
            # 피드백 생성용 프롬프트
            feedback_prompt = f"""
사용자가 "{language}" 언어를 배우고 있습니다. 다음 메시지를 분석해주세요:

사용자 메시지: "{user_message}"
난이도: {difficulty}

다음 JSON 형식으로 피드백을 제공해주세요:
{{
    "level": "excellent|good|needs_improvement",
    "message": "격려 메시지",
    "grammar_feedback": ["문법 교정 사항들"],
    "vocabulary_suggestions": ["유용한 어휘들"],
    "pronunciation_tips": ["발음 팁들"]
}}

간결하고 건설적인 피드백을 제공하세요.
"""

            response = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",  # 피드백은 더 빠른 모델 사용
                messages=[{"role": "user", "content": feedback_prompt}],
                max_tokens=300,
                temperature=0.3,
            )

            feedback_text = response.choices[0].message.content

            try:
                # JSON 파싱
                feedback = json.loads(feedback_text)
                return feedback
            except json.JSONDecodeError:
                # JSON 파싱 실패시 기본 피드백
                return {
                    "level": "good",
                    "message": "좋은 응답입니다! 계속 연습해보세요.",
                    "grammar_feedback": [],
                    "vocabulary_suggestions": [],
                    "pronunciation_tips": [],
                }

        except Exception as e:
            logger.error(f"피드백 생성 오류: {e}")
            return {
                "level": "good",
                "message": "응답을 잘 하셨습니다!",
                "grammar_feedback": [],
                "vocabulary_suggestions": [],
                "pronunciation_tips": [],
            }

    async def generate_scenario_intro(
        self, situation: str, language: str = "en", difficulty: str = "beginner"
    ) -> str:
        """시나리오 시작 메시지 생성"""

        if not self.client:
            # 기본 메시지 반환
            return f"Hello! Let's practice {situation} conversation."

        try:
            prompt = f"""
Create an opening message for a {language} language learning conversation practice.
Situation: {situation}
Difficulty: {difficulty}

The message should:
1. Be welcoming and encouraging
2. Set the scene for the situation
3. Ask an opening question to start the conversation
4. Match the difficulty level

Respond in {language} only.
"""

            response = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=150,
                temperature=0.7,
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            logger.error(f"시나리오 인트로 생성 오류: {e}")
            return f"Hello! Let's practice {situation} conversation."

    def clear_conversation_history(self, session_id: str):
        """대화 히스토리 초기화"""

        if session_id in self.conversation_histories:
            del self.conversation_histories[session_id]
            logger.info(f"대화 히스토리 초기화: {session_id}")

    def get_conversation_summary(self, session_id: str) -> Dict[str, Any]:
        """대화 요약 생성"""

        history = self.conversation_histories.get(session_id, [])

        user_messages = [msg["content"] for msg in history if msg["role"] == "user"]
        ai_messages = [msg["content"] for msg in history if msg["role"] == "assistant"]

        return {
            "total_exchanges": len(user_messages),
            "user_messages": len(user_messages),
            "ai_messages": len(ai_messages),
            "conversation_length": len(history),
            "last_updated": datetime.now().isoformat(),
        }

    async def test_connection(self) -> Dict[str, Any]:
        """OpenAI 연결 테스트"""

        if not self.client:
            return {"connected": False, "error": "API 키가 설정되지 않았습니다"}

        try:
            response = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "user", "content": "Hello, this is a connection test."}
                ],
                max_tokens=50,
            )

            return {
                "connected": True,
                "model": "gpt-3.5-turbo",
                "response": response.choices[0].message.content,
            }

        except Exception as e:
            return {"connected": False, "error": str(e)}


# 전역 인스턴스
openai_service = OpenAIService()
