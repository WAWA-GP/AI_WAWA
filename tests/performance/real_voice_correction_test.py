"""
실제 음성 파일을 사용한 발음 교정 시스템 테스트
- 실제 음성 파일 로드
- 발음 분석
- Voice Cloning
- 교정된 음성 생성
- 결과 비교
"""

import asyncio
import base64
import json
import time
import sys
import uuid
import os
import subprocess
import wave
import tempfile
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

# 환경 변수 로드
from dotenv import load_dotenv

# 프로젝트 루트에서 .env 로드
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))

# .env 파일 경로 명시적으로 지정
env_path = os.path.join(project_root, '.env')
load_dotenv(dotenv_path=env_path)

# 환경 변수 로드 확인
print(f"🔍 .env 파일 경로: {env_path}")
print(f"🔍 .env 파일 존재: {os.path.exists(env_path)}")
print(f"🔍 SUPABASE_URL 설정됨: {'✅' if os.getenv('SUPABASE_URL') else '❌'}")
print(f"🔍 ELEVENLABS_API_KEY 설정됨: {'✅' if os.getenv('ELEVENLABS_API_KEY') else '❌'}")

# 프로젝트 경로 설정
app_dir = os.path.join(project_root, 'app')

sys.path.insert(0, app_dir)
sys.path.insert(0, project_root)

# 서비스 임포트
try:
    from services.voice_cloning_service import voice_cloning_service
    from services.pronunciation_analysis_service import pronunciation_service
    from services.speech_recognition_service import stt_service
    from services.text_to_speech_service import tts_service
    print("✅ 모든 서비스 임포트 성공")
except ImportError as e:
    print(f"❌ 서비스 임포트 실패: {e}")
    sys.exit(1)

class RealVoiceCorrectionTester:
    """실제 음성을 사용한 발음 교정 테스트"""

    def __init__(self):
        self.user_id = str(uuid.uuid4())
        self.test_results = {}
        self.audio_files_dir = "test_audio_files"  # 테스트 음성 파일 디렉토리

        # 테스트 음성 파일 디렉토리 생성
        os.makedirs(self.audio_files_dir, exist_ok=True)

    def load_audio_file_as_base64(self, file_path: str) -> Optional[str]:
        """음성 파일을 Base64로 로드"""
        try:
            if not os.path.exists(file_path):
                print(f"❌ 파일을 찾을 수 없습니다: {file_path}")
                return None

            with open(file_path, 'rb') as f:
                audio_data = f.read()
                audio_base64 = base64.b64encode(audio_data).decode('utf-8')

            print(f"✅ 음성 파일 로드 완료: {file_path}")
            return audio_base64

        except Exception as e:
            print(f"❌ 음성 파일 로드 오류: {e}")
            return None

    def save_base64_to_file(self, audio_base64: str, filename: str) -> str:
        """Base64 음성을 파일로 저장"""
        try:
            audio_data = base64.b64decode(audio_base64)
            file_path = os.path.join(self.audio_files_dir, filename)

            with open(file_path, 'wb') as f:
                f.write(audio_data)

            print(f"✅ 음성 파일 저장: {file_path}")
            return file_path

        except Exception as e:
            print(f"❌ 음성 파일 저장 오류: {e}")
            return ""

    async def test_voice_correction_pipeline(
            self,
            user_voice_file: str,  # 사용자 음성 샘플 (Voice Clone용)
            test_voice_file: str,  # 테스트할 발음 음성
            target_text: str,      # 목표 텍스트
            language: str = "en"
    ) -> Dict:
        """전체 음성 교정 파이프라인 테스트"""

        print(f"\n🎯 음성 교정 파이프라인 테스트 시작")
        print(f"목표 텍스트: '{target_text}'")
        print(f"언어: {language}")

        results = {
            "target_text": target_text,
            "language": language,
            "timestamp": datetime.now().isoformat(),
            "steps": {}
        }

        try:
            # Step 1: 사용자 음성 샘플 로드 (Voice Clone용)
            print(f"\n📁 Step 1: 사용자 음성 샘플 로드")
            user_audio_base64 = self.load_audio_file_as_base64(user_voice_file)
            if not user_audio_base64:
                return {"error": "사용자 음성 샘플 로드 실패"}

            results["steps"]["voice_sample_loaded"] = True

            # Step 2: Voice Clone 생성
            print(f"\n🎭 Step 2: Voice Clone 생성")
            clone_start = time.time()

            clone_result = await voice_cloning_service.create_user_voice_clone(
                user_id=self.user_id,
                voice_sample_base64=user_audio_base64,
                voice_name=f"TestVoice_{self.user_id}"
            )

            clone_time = time.time() - clone_start
            results["steps"]["voice_clone"] = {
                "success": clone_result.get("success", False),
                "voice_id": clone_result.get("voice_id", ""),
                "time_ms": clone_time * 1000,
                "cached": clone_result.get("cached", False)
            }

            if not clone_result.get("success"):
                print(f"❌ Voice Clone 생성 실패: {clone_result.get('error')}")
                return results

            print(f"✅ Voice Clone 생성 완료 (Voice ID: {clone_result.get('voice_id')})")

            # Step 3: 테스트 음성 로드 및 발음 분석
            print(f"\n🔍 Step 3: 발음 분석")
            test_audio_base64 = self.load_audio_file_as_base64(test_voice_file)
            if not test_audio_base64:
                return {"error": "테스트 음성 파일 로드 실패"}

            analysis_start = time.time()

            pronunciation_analysis = await pronunciation_service.analyze_pronunciation_from_base64(
                audio_base64=test_audio_base64,
                target_text=target_text,
                user_level="B1",
                language=language
            )

            analysis_time = time.time() - analysis_start

            results["steps"]["pronunciation_analysis"] = {
                "time_ms": analysis_time * 1000,
                "scores": {
                    "overall": pronunciation_analysis.overall_score,
                    "pitch": pronunciation_analysis.pitch_score,
                    "rhythm": pronunciation_analysis.rhythm_score,
                    "stress": pronunciation_analysis.stress_score,
                    "fluency": pronunciation_analysis.fluency_score
                },
                "feedback": pronunciation_analysis.detailed_feedback,
                "suggestions": pronunciation_analysis.suggestions
            }

            print(f"✅ 발음 분석 완료 - 전체 점수: {pronunciation_analysis.overall_score:.1f}")

            # Step 4: 원본 음성을 STT로 인식
            print(f"\n🎤 Step 4: 원본 음성 STT 인식")
            stt_start = time.time()

            original_stt = await stt_service.recognize_from_base64(
                audio_base64=test_audio_base64,
                language=f"{language}-{language.upper()}" if language == "ko" else f"{language}-US"
            )

            stt_time = time.time() - stt_start

            results["steps"]["original_stt"] = {
                "recognized_text": original_stt or "인식 실패",
                "time_ms": stt_time * 1000,
                "success": original_stt is not None
            }

            print(f"✅ 원본 STT 결과: '{original_stt}'")

            # Step 5: 교정된 음성 생성 (사용자 목소리로)
            print(f"\n🔧 Step 5: 교정된 음성 생성")
            correction_start = time.time()

            # Voice ID를 직접 사용
            voice_id = clone_result.get("voice_id")

            # ElevenLabs API 직접 호출
            import aiohttp

            api_key = os.getenv("ELEVENLABS_API_KEY")
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

            headers = {
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
                "xi-api-key": api_key
            }

            data = {
                "text": target_text,
                "model_id": "eleven_multilingual_v2",
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.75
                }
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data, headers=headers) as response:
                    if response.status == 200:
                        audio_data = await response.read()
                        corrected_audio_base64 = base64.b64encode(audio_data).decode('utf-8')
                        corrected_result = {
                            "success": True,
                            "corrected_audio_base64": corrected_audio_base64
                        }
                    else:
                        error_text = await response.text()
                        corrected_result = {
                            "success": False,
                            "error": f"API 오류 {response.status}: {error_text}"
                        }

            correction_time = time.time() - correction_start

            results["steps"]["corrected_generation"] = {
                "success": corrected_result.get("success", False),
                "time_ms": correction_time * 1000,
                "corrections_applied": ["voice_cloning"]
            }

            if not corrected_result.get("success"):
                print(f"❌ 교정된 음성 생성 실패: {corrected_result.get('error')}")
                return results

            print(f"✅ 교정된 음성 생성 완료")

            # 교정된 음성 파일 저장
            corrected_audio_base64 = corrected_result.get("corrected_audio_base64")
            if corrected_audio_base64:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                corrected_file = f"corrected_{self.user_id}_{timestamp}.mp3"  # mp3로 변경
                corrected_path = self.save_base64_to_file(corrected_audio_base64, corrected_file)
                results["corrected_audio_file"] = corrected_path

            # Step 6: 교정된 음성을 STT로 인식
            print(f"\n🎯 Step 6: 교정된 음성 STT 검증")

            # MP3를 WAV로 변환 (STT는 WAV만 지원)
            import subprocess

            corrected_wav_path = corrected_path.replace('.mp3', '_converted.wav')

            convert_command = [
                'ffmpeg',
                '-i', corrected_path,
                '-ar', '16000',
                '-ac', '1',
                '-acodec', 'pcm_s16le',
                '-y',
                corrected_wav_path
            ]

            subprocess.run(convert_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            # 변환된 WAV 파일을 Base64로 읽기
            with open(corrected_wav_path, 'rb') as f:
                corrected_wav_data = f.read()
                corrected_wav_base64 = base64.b64encode(corrected_wav_data).decode('utf-8')

            corrected_stt_start = time.time()

            corrected_stt = await stt_service.recognize_from_base64(
                audio_base64=corrected_wav_base64,
                language=f"{language}-{language.upper()}" if language == "ko" else f"{language}-US"
            )

            corrected_stt_time = time.time() - corrected_stt_start

            # Step 7: 결과 비교 및 평가
            print(f"\n📊 Step 7: 결과 분석")

            # WER 계산
            original_wer = self.calculate_word_error_rate(target_text, original_stt or "")
            corrected_wer = self.calculate_word_error_rate(target_text, corrected_stt or "")

            # 개선도 계산
            improvement = original_wer - corrected_wer
            improvement_percentage = (improvement / max(original_wer, 0.001)) * 100

            results["evaluation"] = {
                "original_wer": original_wer,
                "corrected_wer": corrected_wer,
                "improvement": improvement,
                "improvement_percentage": improvement_percentage,
                "total_processing_time_ms": (time.time() - clone_start) * 1000
            }

            results["success"] = True

            print(f"✅ 전체 파이프라인 완료!")
            print(f"   원본 WER: {original_wer:.3f}")
            print(f"   교정 WER: {corrected_wer:.3f}")
            print(f"   개선도: {improvement_percentage:.1f}%")

            return results

        except Exception as e:
            print(f"❌ 파이프라인 오류: {e}")
            results["error"] = str(e)
            return results

    def calculate_word_error_rate(self, reference: str, hypothesis: str) -> float:
        """Word Error Rate (WER) 계산"""
        if not reference or not hypothesis:
            return 1.0

        ref_words = reference.lower().split()
        hyp_words = hypothesis.lower().split()

        # Levenshtein distance 기반 WER 계산
        d = [[0] * (len(hyp_words) + 1) for _ in range(len(ref_words) + 1)]

        for i in range(len(ref_words) + 1):
            d[i][0] = i
        for j in range(len(hyp_words) + 1):
            d[0][j] = j

        for i in range(1, len(ref_words) + 1):
            for j in range(1, len(hyp_words) + 1):
                if ref_words[i-1] == hyp_words[j-1]:
                    d[i][j] = d[i-1][j-1]
                else:
                    d[i][j] = min(
                        d[i-1][j] + 1,    # deletion
                        d[i][j-1] + 1,    # insertion
                        d[i-1][j-1] + 1   # substitution
                    )

        return d[len(ref_words)][len(hyp_words)] / len(ref_words) if ref_words else 0

    def generate_test_report(self, results: Dict):
        """테스트 결과 리포트 생성"""
        print("\n" + "=" * 80)
        print("📋 실제 음성 교정 테스트 결과 리포트")
        print("=" * 80)

        if "error" in results:
            print(f"❌ 테스트 실패: {results['error']}")
            return

        print(f"\n🎯 테스트 대상:")
        print(f"   목표 텍스트: '{results['target_text']}'")
        print(f"   언어: {results['language']}")
        print(f"   테스트 시간: {results['timestamp']}")

        print(f"\n📊 처리 단계별 결과:")

        steps = results.get("steps", {})

        # Voice Clone
        if "voice_clone" in steps:
            vc = steps["voice_clone"]
            status = "✅" if vc["success"] else "❌"
            cached_info = " (캐시됨)" if vc.get("cached") else ""
            print(f"   {status} Voice Clone: {vc['time_ms']:.0f}ms{cached_info}")

        # 발음 분석
        if "pronunciation_analysis" in steps:
            pa = steps["pronunciation_analysis"]
            print(f"   ✅ 발음 분석: {pa['time_ms']:.0f}ms")
            print(f"      전체: {pa['scores']['overall']:.1f}, 피치: {pa['scores']['pitch']:.1f}")
            print(f"      리듬: {pa['scores']['rhythm']:.1f}, 강세: {pa['scores']['stress']:.1f}")

        # STT 결과
        if "original_stt" in steps:
            stt = steps["original_stt"]
            status = "✅" if stt["success"] else "❌"
            print(f"   {status} 원본 STT: '{stt['recognized_text']}' ({stt['time_ms']:.0f}ms)")

        # 교정된 음성 생성
        if "corrected_generation" in steps:
            cg = steps["corrected_generation"]
            status = "✅" if cg["success"] else "❌"
            print(f"   {status} 교정 음성 생성: {cg['time_ms']:.0f}ms")
            if cg.get("corrections_applied"):
                print(f"      적용된 교정: {', '.join(cg['corrections_applied'])}")

        # 교정된 STT 결과
        if "corrected_stt" in steps:
            cstt = steps["corrected_stt"]
            status = "✅" if cstt["success"] else "❌"
            print(f"   {status} 교정 STT: '{cstt['recognized_text']}' ({cstt['time_ms']:.0f}ms)")

        # 전체 평가
        if "evaluation" in results:
            eval_data = results["evaluation"]
            print(f"\n🎯 성능 평가:")
            print(f"   원본 WER: {eval_data['original_wer']:.3f}")
            print(f"   교정 WER: {eval_data['corrected_wer']:.3f}")
            print(f"   개선도: {eval_data['improvement_percentage']:.1f}%")
            print(f"   전체 처리 시간: {eval_data['total_processing_time_ms']:.0f}ms")

            # 성능 등급
            if eval_data['improvement_percentage'] > 20:
                grade = "🏆 우수한 개선"
            elif eval_data['improvement_percentage'] > 10:
                grade = "🥈 양호한 개선"
            elif eval_data['improvement_percentage'] > 0:
                grade = "🥉 약간의 개선"
            else:
                grade = "⚠️ 개선 효과 미미"

            print(f"   개선 등급: {grade}")

        # 결과 파일 저장
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"voice_correction_test_{timestamp}.json"

        try:
            # 결과를 깨끗하게 정리
            clean_results = json.loads(json.dumps(results, ensure_ascii=True))

            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(clean_results, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ JSON 저장 오류: {e}")
            # ASCII로 강제 저장
            with open(filename, 'w', encoding='ascii', errors='ignore') as f:
                json.dump(results, f, ensure_ascii=True, indent=2)

    async def run_interactive_test(self):
        """대화형 테스트 실행"""
        print("🎙️ 실제 음성을 사용한 발음 교정 시스템 테스트")
        print("=" * 60)

        # 사용자 입력 받기
        print("\n📁 음성 파일 경로 입력:")
        user_voice_file = input("사용자 음성 샘플 파일 경로 (Voice Clone용): ").strip()
        test_voice_file = input("테스트할 발음 음성 파일 경로: ").strip()
        target_text = input("목표 텍스트: ").strip()
        language = input("언어 (ko/en/ja/zh/fr, 기본값 en): ").strip() or "en"

        # 파일 존재 확인
        if not os.path.exists(user_voice_file):
            print(f"❌ 사용자 음성 파일을 찾을 수 없습니다: {user_voice_file}")
            return

        if not os.path.exists(test_voice_file):
            print(f"❌ 테스트 음성 파일을 찾을 수 없습니다: {test_voice_file}")
            return

        # 테스트 실행
        results = await self.test_voice_correction_pipeline(
            user_voice_file=user_voice_file,
            test_voice_file=test_voice_file,
            target_text=target_text,
            language=language
        )

        # 결과 출력
        self.generate_test_report(results)

async def main():
    """메인 실행 함수"""
    tester = RealVoiceCorrectionTester()

    print("선택하세요:")
    print("1. 대화형 테스트")
    print("2. 예제 테스트 (미리 준비된 파일 사용)")

    choice = input("선택 (1 또는 2): ").strip()

    if choice == "1":
        await tester.run_interactive_test()
    elif choice == "2":
        # 예제 파일이 있다면 자동 테스트
        print("❗ 예제 파일이 필요합니다. test_audio_files 디렉토리에 파일을 넣어주세요.")
        print("예상 파일명:")
        print("  - user_voice_sample.wav (사용자 음성 샘플)")
        print("  - test_pronunciation.wav (테스트할 발음)")

        # 예제 파일이 있는지 확인
        example_user_file = "test_audio_files/user_voice_sample.wav"
        example_test_file = "test_audio_files/test_pronunciation.wav"

        if os.path.exists(example_user_file) and os.path.exists(example_test_file):
            target_text = input("목표 텍스트를 입력하세요: ").strip()
            # 잘못된 문자 제거
            target_text = target_text.encode('utf-8', errors='ignore').decode('utf-8', errors='ignore')

            results = await tester.test_voice_correction_pipeline(
                user_voice_file=example_user_file,
                test_voice_file=example_test_file,
                target_text=target_text,
                language="en"
            )
            tester.generate_test_report(results)
        else:
            print("❌ 예제 파일을 찾을 수 없습니다.")
    else:
        print("❌ 잘못된 선택입니다.")

if __name__ == "__main__":
    asyncio.run(main())
