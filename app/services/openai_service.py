# services/openai_service.py
# OpenAI GPT-4 연동 서비스

import asyncio
import json
import logging
import os
from typing import Dict, List, Optional, Any
from datetime import datetime
import openai
import base64
import tempfile
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
                "airport": """You are an actor playing the role of a check-in agent at an airport. Your only goal is to create a 100% realistic and immersive role-play.

--- ABSOLUTE RULES for the In-Character Response part ---
1.  **NEVER break character.** You are a check-in agent, not an AI or a language teacher.
2.  **NEVER mention practice, learning, lessons, simulation, or role-play.**
3.  **NEVER use phrases like "Let's practice...", "Great job!", "Well done!", or "How about we try...".** Do not encourage or praise the user. Simply respond to them as a real, professional agent would.
4.  Interact with the user as a real traveler. Keep your responses concise and to the point, as a busy agent would.

You must start the scene immediately. Your first line is: "Next in line, please. Hi there, where are you flying to today?"
""",
                "restaurant": """You are an actor playing the role of a server at a restaurant. Your only goal is to create a 100% realistic and immersive role-play.

--- ABSOLUTE RULES for the In-Character Response part ---
1.  **NEVER break character.** You are a server, not an AI or a language teacher.
2.  **NEVER mention practice, learning, lessons, simulation, or role-play.**
3.  **NEVER use phrases like "Let's practice..." or "Good job!".** Do not encourage or praise the user. Simply respond to them as a real server would.
4.  Interact with the user as a real customer. Be polite and efficient.

You must start the scene immediately. Your first line is: "Hi, welcome! Just one for today?"
""",
                "hotel": """You are an actor playing the role of a front desk clerk at a hotel. Your only goal is to create a 100% realistic and immersive role-play.

--- ABSOLUTE RULES for the In-Character Response part ---
1.  **NEVER break character.** You are a hotel clerk, not an AI or a language teacher.
2.  **NEVER mention practice, learning, lessons, simulation, or role-play.
3.  **NEVER use encouraging or teaching phrases.** Simply perform your role.
4.  Interact with the user as a real hotel guest.

You must start the scene immediately. Your first line is: "Good afternoon, welcome to the Grand Hotel. How can I help you?"
""",
                "street": """You are an actor playing the role of a local person on a busy street who has just been stopped by a tourist (the user). Your only goal is to create a 100% realistic role-play.

--- ABSOLUTE RULES for the In-Character Response part ---
1.  **NEVER break character.** You are a local person, not an AI or a language teacher.
2.  **NEVER mention practice, learning, lessons, simulation, or role-play.**
3.  **DO NOT start the conversation.** The user will ask you for help. Your first response should be a natural reaction to being stopped on the street, like "Oh, sure, I can help. What are you looking for?"
""",
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
            translate_to: Optional[str] = None
    ) -> Dict[str, Any]:
        """(수정됨) GPT 응답 생성과 번역을 병렬로 처리하여 속도를 개선합니다."""

        if not self.client:
            return {"success": False, "error": "OpenAI API 키가 설정되지 않았습니다.", "fallback": True}

        try:
            # --- 1. 메인 AI 응답 생성 작업 정의 ---
            system_prompt = self._get_system_prompt(situation, language, difficulty)
            conversation = self._get_conversation_history(session_id)
            messages = [{"role": "system", "content": system_prompt}] + conversation + [{"role": "user", "content": user_message}]

            logger.info(f"GPT-4-Turbo 요청 시작: {session_id}")
            main_response_task = self.client.chat.completions.create(
                model="gpt-4-turbo",  # ◀◀◀ [속도 개선] gpt-4 보다 훨씬 빠른 gpt-4-turbo 모델 사용
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )

            # --- 2. 메인 AI 응답과 번역을 동시에 실행 ---
            main_response = await main_response_task
            ai_message = main_response.choices[0].message.content
            logger.info(f"GPT-4-Turbo 응답 수신: {session_id}")

            translated_text = None
            if translate_to and ai_message:
                try:
                    # 번역할 대화 부분만 추출
                    conversational_part = ai_message.split("=======")[0].strip()

                    # 번역 작업을 비동기 태스크로 만듦
                    translation_task = self.client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=[
                            {"role": "system", "content": f"You are a helpful translator. Translate the following text to {translate_to}."},
                            {"role": "user", "content": conversational_part}
                        ],
                        max_tokens=300,
                        temperature=0.1,
                    )

                    # 번역이 완료될 때까지 기다림
                    translation_response = await translation_task
                    translated_text = translation_response.choices[0].message.content
                    logger.info("번역 작업 완료.")

                except Exception as e:
                    logger.error(f"번역 API 호출 병렬 처리 중 오류: {e}")
                    translated_text = "번역 중 오류가 발생했습니다."

            # --- 3. 결과 종합 및 반환 ---
            self._update_conversation_history(session_id, user_message, ai_message)

            return {
                "success": True,
                "ai_message": ai_message,
                "translated_text": translated_text,
                "feedback": await self._analyze_user_input(user_message, ai_message, language, difficulty),
                "tokens_used": main_response.usage.total_tokens,
                "model": "gpt-4-turbo",
            }

        except Exception as e:
            logger.error(f"GPT-4-Turbo 요청 오류: {e}")
            return {"success": False, "error": f"AI 응답 생성 중 오류: {str(e)}", "fallback": True}


    def _get_system_prompt(self, situation: str, language: str, difficulty: str) -> str:
        """상황과 언어, 그리고 원하는 출력 형식에 맞는 시스템 프롬프트를 생성합니다."""

        # 1. 기존과 동일하게 기본 역할 프롬프트를 가져옵니다.
        base_prompt = self.system_prompts.get(language, self.system_prompts["en"])
        situation_prompt = base_prompt.get(situation, base_prompt.get("airport", ""))

        # 2. [핵심] '상황 적절성' 판단 로직이 추가된 새로운 지시문입니다.
        format_instructions = f"""

Your response MUST strictly follow this format, with no exceptions:

1.  **In-Character Response:** [First, provide ONLY your natural, in-character conversational reply.]
2.  **Separator:** After your reply, you MUST insert a single blank line, then this exact separator line, then another single blank line. The separator is:
    ======== Recommended ========
3.  **Feedback JSON (in Korean):** Below the separator, analyze the user's last message and provide a JSON object with feedback in KOREAN.
    - **First, check for contextual relevance.** Is the user's message appropriate for the current '{situation}' situation?
    - **If the message is NOT relevant:**
        - The JSON object MUST contain two keys: "상황 피드백" and "추천 상황".
        - "상황 피드백": Explain in Korean why the user's message is not suitable.
        - "추천 상황": Analyze the user's words. The value for this key MUST be one of the following strings: ["airport", "restaurant", "hotel", "street"]. If the user's words do not clearly match any of these four options, the value MUST be null.
    - **If the message IS relevant:**
        - The JSON object MUST contain two keys: "문법 피드백" and "추천 표현".
        - "문법 피드백": If there are errors, explain them and provide the corrected sentence. If perfect, provide an encouraging message.
        - "추천 표현": Suggest 1-2 alternative, natural phrases (in the original language) with a brief Korean translation.

--- EXAMPLE OUTPUT (Irrelevant) ---
I'm sorry, I don't quite understand. Are you ready to order?

======== Recommended ========

{{
    "상황 피드백": "• '탑승권(boarding pass)'은 공항에서 사용하는 단어입니다. 지금은 식당에서 주문하는 상황이에요.",
    "추천 상황": "airport"
}}

--- EXAMPLE OUTPUT (Relevant) ---
Of course, I can help with that. Your gate is B52, located in the next concourse.

======== Recommended ========

{{
    "문법 피드백": "• \\"I looking for...\\" 대신 \\"I am looking for...\\" 또는 \\"I'm looking for...\\"가 올바른 표현입니다.",
    "추천 표현": [
        "Could you tell me where gate B52 is? (B52번 게이트가 어디인지 알려주시겠어요?)"
    ]
}}
---
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
            self,
            situation: str,
            language: str = "en",
            difficulty: str = "beginner",
            translate_to: Optional[str] = None
    ) -> Dict[str, Optional[str]]:
        """시나리오 시작 메시지 생성"""

        if not self.client:
            return {
                'original': f"Hello! Let's practice {situation} conversation.",
                'translated': None
            }

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
                max_tokens=300,
                temperature=0.7,
            )

            original_text = response.choices[0].message.content.strip()
            translated_text = None

            if translate_to and original_text:
                try:
                    translation_response = await self.client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=[
                            {"role": "system", "content": f"You are a helpful translator. Translate the following text to {translate_to}."},
                            {"role": "user", "content": original_text}
                        ],
                        max_tokens=400,
                        temperature=0.1,
                    )
                    translated_text = translation_response.choices[0].message.content
                except Exception as e:
                    logger.error(f"첫 메시지 번역 오류: {e}")
                    translated_text = "번역 중 오류 발생"

            return {'original': original_text, 'translated': translated_text}

        except Exception as e:
            logger.error(f"시나리오 인트로 생성 오류: {e}")
            return {
                'original': f"Hello! Let's practice {situation} conversation.",
                'translated': None
            }

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

    async def transcribe_audio_base64(self, audio_base64: str, language: str = "en") -> str:
        """Base64 오디오를 Whisper를 통해 텍스트로 변환합니다."""
        if not self.client:
            raise Exception("OpenAI client가 초기화되지 않았습니다.")

        try:
            # Base64를 디코딩하여 바이너리 데이터로 변환
            audio_data = base64.b64decode(audio_base64)

            # 바이너리 데이터를 임시 파일로 저장 (Whisper API는 파일 입력을 받음)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_audio_file:
                temp_audio_file.write(audio_data)
                temp_file_path = temp_audio_file.name

            try:
                # 임시 파일을 열어 API에 전송
                with open(temp_file_path, "rb") as audio_file:
                    transcription = await self.client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        language=language
                    )
                logger.info(f"Whisper 인식 결과: {transcription.text}")
                return transcription.text
            finally:
                # 임시 파일 삭제
                os.unlink(temp_file_path)

        except Exception as e:
            logger.error(f"Whisper API 호출 오류: {e}")
            return ""

    # ▼▼▼ [2/2] GPT-4 피드백 생성 함수 추가 ▼▼▼
    async def get_pronunciation_feedback(self, target_text: str, transcribed_text: str) -> Dict:
        """GPT-4를 사용하여 발음 피드백 JSON을 생성합니다."""
        if not self.client:
            raise Exception("OpenAI client가 초기화되지 않았습니다.")

        # GPT-4에게 보낼 프롬프트(지시문)
        prompt = f"""
        You are an expert English pronunciation tutor AI.
        A student was asked to say the following sentence (the 'target text'):
        TARGET_TEXT: "{target_text}"

        The student's actual pronunciation was transcribed by an AI as follows (the 'transcribed text'):
        TRANSCRIBED_TEXT: "{transcribed_text}"

        Based ONLY on the differences between the TARGET_TEXT and the TRANSCRIBED_TEXT, please provide a brief analysis of the likely pronunciation errors.
        Your response MUST be a JSON object with the following exact keys: "detailed_feedback", "suggestions", "mispronounced_words".
        - "detailed_feedback": A list of strings, explaining the likely errors in Korean.
        - "suggestions": A list of strings, providing actionable tips for improvement in Korean.
        - "mispronounced_words": A list of strings, containing only the specific words from the TARGET_TEXT that were likely mispronounced.

        If the two texts are identical, provide positive feedback and leave "mispronounced_words" as an empty list. Now, analyze the texts above and provide your JSON response.
        """

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4-turbo",  # JSON 모드를 지원하는 최신 모델 사용 권장
                messages=[
                    {"role": "system", "content": "You are a helpful assistant designed to output JSON."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"} # ✅ JSON 형식으로 응답을 강제
            )
            feedback_json_str = response.choices[0].message.content
            logger.info(f"GPT-4 피드백 (JSON): {feedback_json_str}")
            return json.loads(feedback_json_str)

        except Exception as e:
            logger.error(f"GPT-4 피드백 생성 오류: {e}")
            return {
                "detailed_feedback": ["피드백 생성 중 오류가 발생했습니다."],
                "suggestions": ["잠시 후 다시 시도해주세요."],
                "mispronounced_words": []
            }

    async def get_grammar_feedback(self, user_message: str, level: str, language: str) -> Dict:
        """GPT를 사용하여 사용자의 발화 내용에 대한 문법 피드백 JSON을 생성합니다."""
        if not self.client:
            raise Exception("OpenAI client가 초기화되지 않았습니다.")

        prompt = f"""
        You are an expert {language} language tutor AI. A student at the '{level}' level has spoken the following sentence:
        
        "{user_message}"

        Your task is to correct any grammatical errors and provide helpful feedback.
        Your response MUST be a JSON object with the following exact keys: "corrected_text", "grammar_feedback", "vocabulary_suggestions".

        - "corrected_text": The grammatically correct version of the student's sentence. If it's already correct, return the original sentence.
        - "grammar_feedback": A list of strings, explaining the grammatical errors and corrections in Korean. If there are no errors, provide an encouraging message like "문법적으로 완벽한 문장입니다!".
        - "vocabulary_suggestions": A list of strings, suggesting alternative words or more natural expressions in Korean.

        Now, analyze the sentence and provide your JSON response.
        """

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant designed to output JSON."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            feedback_json_str = response.choices[0].message.content
            logger.info(f"GPT-4 문법 피드백 (JSON): {feedback_json_str}")

            feedback_data = json.loads(feedback_json_str)

            # ▼▼▼ [핵심 수정] AI가 만든 불필요한 앞뒤 공백/줄바꿈을 제거하는 코드 ▼▼▼
            if 'grammar_feedback' in feedback_data and isinstance(feedback_data['grammar_feedback'], list):
                # .strip() 함수로 각 항목의 앞뒤 공백과 줄바꿈을 모두 제거합니다.
                feedback_data['grammar_feedback'] = [item.strip() for item in feedback_data['grammar_feedback']]

            if 'vocabulary_suggestions' in feedback_data and isinstance(feedback_data['vocabulary_suggestions'], list):
                feedback_data['vocabulary_suggestions'] = [item.strip() for item in feedback_data['vocabulary_suggestions']]
            # ▲▲▲ 여기까지 수정 ▲▲▲

            return feedback_data

        except Exception as e:
            logger.error(f"GPT-4 문법 피드백 생성 오류: {e}")
            return {
                "corrected_text": user_message,
                "grammar_feedback": ["피드백 생성 중 오류가 발생했습니다."],
                "vocabulary_suggestions": ["잠시 후 다시 시도해주세요."]
            }


# 전역 인스턴스
openai_service = OpenAIService()
