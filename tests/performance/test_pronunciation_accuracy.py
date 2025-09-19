"""
발음 교정 시스템 정확도 테스트 도구 - 경로 수정 버전
저장된 데이터베이스 데이터를 사용하여 교정 시스템의 정확도를 측정합니다.
"""

import asyncio
import os
import sys
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging

# 경로 설정 - test_current_system.py와 동일한 방식 사용
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))  # 2단계 상위로
app_dir = os.path.join(project_root, 'app')

# Python path에 추가
sys.path.insert(0, app_dir)
sys.path.insert(0, project_root)

print(f"현재 디렉토리: {current_dir}")
print(f"프로젝트 루트: {project_root}")
print(f"앱 디렉토리: {app_dir}")

# 서비스 모듈들 임포트 - 안전한 임포트 방식 적용
try:
    from services.pronunciation_data_service import pronunciation_data_service
    print("✅ pronunciation_data_service 임포트 성공")
except ImportError as e:
    print(f"❌ pronunciation_data_service 임포트 실패: {e}")
    pronunciation_data_service = None

try:
    from services.voice_cloning_service import voice_cloning_service
    print("✅ voice_cloning_service 임포트 성공")
except ImportError as e:
    print(f"❌ voice_cloning_service 임포트 실패: {e}")
    voice_cloning_service = None

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class PronunciationAccuracyTester:
    """발음 교정 정확도 테스터"""
    
    def __init__(self):
        self.data_service = pronunciation_data_service
        self.voice_service = voice_cloning_service
        self.test_results = []
        
        # 서비스 사용 가능성 확인
        self.services_available = {
            'data_service': pronunciation_data_service is not None,
            'voice_service': voice_cloning_service is not None
        }
        
    async def run_full_accuracy_test(self, limit: int = 30) -> Dict:
        """전체 정확도 테스트 실행"""
        
        logger.info("🧪 발음 교정 정확도 테스트 시작")
        
        # 서비스 가용성 확인
        if not self.services_available['data_service']:
            logger.error("❌ pronunciation_data_service를 사용할 수 없습니다")
            return {"error": "필수 서비스 불가: pronunciation_data_service"}
        
        try:
            # 1. 데이터베이스에서 테스트 데이터 수집
            test_data = await self._collect_test_data(limit)
            
            if not test_data:
                logger.warning("테스트할 데이터가 없습니다.")
                return {"error": "테스트 데이터 없음"}
            
            logger.info(f"📊 {len(test_data)}개 세션 데이터로 테스트 진행")
            
            # 2. 각 세션의 정확도 평가
            accuracy_results = []
            for session in test_data:
                result = await self._evaluate_session_accuracy(session)
                if result:
                    accuracy_results.append(result)
            
            # 3. 전체 결과 분석
            final_report = self._generate_accuracy_report(accuracy_results)
            
            # 4. 결과 저장
            await self._save_test_results(final_report)
            
            return final_report
            
        except Exception as e:
            logger.error(f"정확도 테스트 오류: {e}")
            return {"error": str(e)}
    
    async def _collect_test_data(self, limit: int) -> List[Dict]:
        """테스트용 데이터 수집 (교정 전후 데이터가 모두 있는 세션)"""
        
        try:
            # Supabase 연결 확인
            if not self.data_service.supabase:
                logger.error("Supabase 연결 없음")
                return []
            
            # 발음 세션과 연관된 모든 데이터 조회
            response = self.data_service.supabase.table('pronunciation_sessions').select('''
                id,
                session_id,
                user_id,
                target_text,
                language,
                user_level,
                created_at,
                pronunciation_analysis_results (
                    overall_score,
                    pitch_score,
                    rhythm_score,
                    stress_score,
                    fluency_score,
                    detailed_feedback,
                    suggestions,
                    confidence
                ),
                pronunciation_audio_files (
                    audio_type,
                    duration_seconds,
                    file_size_bytes
                )
            ''').order('created_at', desc=True).limit(limit * 2).execute()  # 여유있게 가져와서 필터링
            
            valid_sessions = []
            for session in response.data:
                # 분석 결과와 오디오 파일이 모두 있는지 확인
                has_analysis = bool(session.get('pronunciation_analysis_results'))
                audio_files = session.get('pronunciation_audio_files', [])
                has_audio = len(audio_files) > 0
                
                if has_analysis and has_audio:
                    valid_sessions.append(session)
                
                if len(valid_sessions) >= limit:
                    break
            
            logger.info(f"✅ {len(valid_sessions)}개 유효한 세션 수집")
            return valid_sessions
            
        except Exception as e:
            logger.error(f"데이터 수집 오류: {e}")
            return []
    
    async def _evaluate_session_accuracy(self, session: Dict) -> Optional[Dict]:
        """개별 세션의 교정 정확도 평가"""
        
        try:
            session_id = session['session_id']
            target_text = session['target_text']
            user_level = session['user_level']
            language = session.get('language', 'en')
            
            # 분석 결과 추출
            analysis_results = session.get('pronunciation_analysis_results', [])
            if not analysis_results:
                return None
                
            analysis = analysis_results[0]  # 첫 번째 분석 결과 사용
            
            # 교정 필요도 계산 (점수가 낮을수록 교정이 더 필요)
            correction_needed = self._calculate_correction_need(analysis)
            
            # 실제 적용된 교정 평가
            correction_accuracy = self._evaluate_correction_quality(analysis, target_text, language)
            
            # 사용자 레벨별 가중치 적용
            level_weight = self._get_level_weight(user_level)
            
            # 최종 정확도 점수 계산
            final_accuracy = (correction_accuracy * level_weight) * (correction_needed / 100)
            
            return {
                "session_id": session_id,
                "target_text": target_text,
                "user_level": user_level,
                "language": language,
                "original_scores": {
                    "overall": analysis.get('overall_score', 0),
                    "pitch": analysis.get('pitch_score', 0),
                    "rhythm": analysis.get('rhythm_score', 0),
                    "stress": analysis.get('stress_score', 0),
                    "fluency": analysis.get('fluency_score', 0)
                },
                "correction_needed": correction_needed,
                "correction_accuracy": correction_accuracy,
                "final_accuracy": final_accuracy,
                "confidence": analysis.get('confidence', 0)
            }
            
        except Exception as e:
            logger.error(f"세션 {session.get('session_id', 'unknown')} 평가 오류: {e}")
            return None
    
    def _calculate_correction_need(self, analysis: Dict) -> float:
        """교정 필요도 계산 (0-100, 높을수록 교정이 많이 필요)"""
        
        scores = [
            analysis.get('overall_score', 50),
            analysis.get('pitch_score', 50),
            analysis.get('rhythm_score', 50),
            analysis.get('stress_score', 50),
            analysis.get('fluency_score', 50)
        ]
        
        avg_score = sum(scores) / len(scores)
        
        # 점수가 낮을수록 교정 필요도가 높음
        correction_need = 100 - avg_score
        return max(10, min(100, correction_need))  # 10-100 범위로 제한
    
    def _evaluate_correction_quality(self, analysis: Dict, target_text: str, language: str) -> float:
        """교정 품질 평가"""
        
        quality_score = 70  # 기본 점수
        
        # 1. 점수별 교정 적절성 평가
        pitch_score = analysis.get('pitch_score', 50)
        stress_score = analysis.get('stress_score', 50)
        rhythm_score = analysis.get('rhythm_score', 50)
        
        # 점수가 낮은 영역에 적절한 교정이 적용되었는지 평가
        corrections_needed = []
        if pitch_score < 70:
            corrections_needed.append('pitch')
            quality_score += 10  # 피치 교정이 필요한 상황에서 교정 적용
        
        if stress_score < 70:
            corrections_needed.append('stress')
            quality_score += 10  # 강세 교정 적용
            
        if rhythm_score < 70:
            corrections_needed.append('rhythm')
            quality_score += 10  # 리듬 교정 적용
        
        # 2. 텍스트 복잡도 고려
        word_count = len(target_text.split())
        if word_count > 5:
            quality_score += 5  # 긴 텍스트 처리 가점
        
        # 3. 언어별 난이도 고려
        language_difficulty = {
            'en': 1.0,
            'ko': 1.2,
            'ja': 1.3,
            'zh': 1.4,
            'fr': 1.1
        }
        
        quality_score *= language_difficulty.get(language, 1.0)
        
        return min(100, max(30, quality_score))
    
    def _get_level_weight(self, user_level: str) -> float:
        """사용자 레벨별 가중치"""
        
        weights = {
            'A1': 1.2,  # 초급자는 관대하게 평가
            'A2': 1.1,
            'B1': 1.0,  # 기준
            'B2': 0.9,
            'C1': 0.8,
            'C2': 0.7   # 고급자는 엄격하게 평가
        }
        
        return weights.get(user_level, 1.0)
    
    def _generate_accuracy_report(self, results: List[Dict]) -> Dict:
        """최종 정확도 리포트 생성"""
        
        if not results:
            return {"error": "분석할 결과가 없습니다"}
        
        # 전체 정확도
        total_accuracy = sum(r['final_accuracy'] for r in results) / len(results)
        
        # 레벨별 정확도
        level_accuracy = {}
        for level in ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']:
            level_results = [r for r in results if r['user_level'] == level]
            if level_results:
                level_accuracy[level] = {
                    'accuracy': sum(r['final_accuracy'] for r in level_results) / len(level_results),
                    'sample_count': len(level_results)
                }
        
        # 언어별 정확도
        language_accuracy = {}
        for lang in ['ko', 'en', 'ja', 'zh', 'fr']:
            lang_results = [r for r in results if r['language'] == lang]
            if lang_results:
                language_accuracy[lang] = {
                    'accuracy': sum(r['final_accuracy'] for r in lang_results) / len(lang_results),
                    'sample_count': len(lang_results)
                }
        
        # 문제가 되는 패턴 식별
        problem_patterns = self._identify_problem_patterns(results)
        
        # 정확도 분포
        accuracy_distribution = {
            'excellent (90-100)': len([r for r in results if r['final_accuracy'] >= 90]),
            'good (80-89)': len([r for r in results if 80 <= r['final_accuracy'] < 90]),
            'fair (70-79)': len([r for r in results if 70 <= r['final_accuracy'] < 80]),
            'poor (<70)': len([r for r in results if r['final_accuracy'] < 70])
        }
        
        return {
            "test_summary": {
                "total_samples": len(results),
                "overall_accuracy": round(total_accuracy, 2),
                "test_date": datetime.now().isoformat(),
                "confidence_level": sum(r['confidence'] for r in results) / len(results),
                "services_available": self.services_available
            },
            "accuracy_by_level": level_accuracy,
            "accuracy_by_language": language_accuracy,
            "accuracy_distribution": accuracy_distribution,
            "problem_patterns": problem_patterns,
            "detailed_results": results[:10],  # 상위 10개 결과만 포함
            "recommendations": self._generate_recommendations(total_accuracy, problem_patterns)
        }
    
    def _identify_problem_patterns(self, results: List[Dict]) -> List[Dict]:
        """문제가 되는 패턴 식별"""
        
        problems = []
        
        # 낮은 정확도 패턴 찾기
        low_accuracy_results = [r for r in results if r['final_accuracy'] < 70]
        
        if len(low_accuracy_results) > len(results) * 0.3:  # 30% 이상이 낮은 정확도
            problems.append({
                "pattern": "전반적 정확도 부족",
                "severity": "high",
                "affected_samples": len(low_accuracy_results),
                "description": "교정 시스템의 전반적인 정확도가 낮습니다"
            })
        
        # 특정 레벨에서의 문제
        for level in ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']:
            level_results = [r for r in results if r['user_level'] == level]
            if level_results and len(level_results) >= 3:
                avg_accuracy = sum(r['final_accuracy'] for r in level_results) / len(level_results)
                if avg_accuracy < 65:
                    problems.append({
                        "pattern": f"{level} 레벨 정확도 부족",
                        "severity": "medium",
                        "affected_samples": len(level_results),
                        "description": f"{level} 레벨 사용자에 대한 교정 정확도가 낮습니다"
                    })
        
        return problems
    
    def _generate_recommendations(self, overall_accuracy: float, problems: List[Dict]) -> List[str]:
        """개선 권장사항 생성"""
        
        recommendations = []
        
        if overall_accuracy < 70:
            recommendations.append("SSML 태그를 활용하여 더 정밀한 발음 교정을 구현하세요")
            recommendations.append("발음 분석 알고리즘의 정확도를 개선하세요")
        
        if overall_accuracy < 80:
            recommendations.append("사용자 레벨별 교정 전략을 세분화하세요")
            recommendations.append("언어별 특성을 반영한 교정 로직을 강화하세요")
        
        # 문제 패턴 기반 권장사항
        for problem in problems:
            if "레벨" in problem["pattern"]:
                recommendations.append(f"특정 레벨 사용자를 위한 맞춤형 교정 개선 필요")
            
        if not recommendations:
            recommendations.append("현재 시스템의 정확도가 양호합니다. 지속적인 모니터링을 권장합니다")
        
        return list(set(recommendations))  # 중복 제거
    
    async def _save_test_results(self, report: Dict) -> bool:
        """테스트 결과 저장"""
        
        try:
            # JSON 파일로 저장
            filename = f"pronunciation_accuracy_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            
            logger.info(f"📄 테스트 결과가 {filename}에 저장되었습니다")
            return True
            
        except Exception as e:
            logger.error(f"결과 저장 오류: {e}")
            return False

    async def run_simplified_test(self):
        """서비스 연결 문제시 간단한 테스트 실행"""
        print("\n🔧 간단한 연결 테스트 실행")
        print("-" * 40)
        
        # 서비스 가용성 확인
        for service_name, available in self.services_available.items():
            if available:
                print(f"✅ {service_name}: 사용 가능")
            else:
                print(f"❌ {service_name}: 사용 불가")
        
        if not any(self.services_available.values()):
            print("⚠️  모든 필수 서비스를 사용할 수 없습니다.")
            print("    경로 설정이나 의존성을 확인해주세요.")
            return False
        
        return True

# 메인 실행 함수
async def main():
    """메인 테스트 실행"""
    
    print("🎯 발음 교정 시스템 정확도 테스트")
    print("=" * 50)
    
    tester = PronunciationAccuracyTester()
    
    # 간단한 연결 테스트 먼저 실행
    connection_ok = await tester.run_simplified_test()
    
    if not connection_ok:
        print("\n연결 테스트에서 문제가 발견되었습니다.")
        return
    
    # 실제 테스트 실행
    try:
        results = await tester.run_full_accuracy_test(limit=10)  # 10개 샘플로 테스트
        
        if "error" in results:
            print(f"❌ 테스트 실패: {results['error']}")
            return
        
        # 결과 출력
        summary = results["test_summary"]
        print(f"\n📊 테스트 결과:")
        print(f"   총 샘플 수: {summary['total_samples']}개")
        print(f"   전체 정확도: {summary['overall_accuracy']}%")
        print(f"   신뢰도: {summary.get('confidence_level', 0):.2f}")
        
        print(f"\n📈 정확도 분포:")
        for grade, count in results["accuracy_distribution"].items():
            print(f"   {grade}: {count}개")
        
        if results["problem_patterns"]:
            print(f"\n⚠️  발견된 문제:")
            for problem in results["problem_patterns"]:
                print(f"   - {problem['pattern']}: {problem['description']}")
        
        print(f"\n💡 권장사항:")
        for rec in results["recommendations"]:
            print(f"   - {rec}")
        
        print(f"\n✅ 상세 결과가 JSON 파일로 저장되었습니다.")
        
    except Exception as e:
        print(f"❌ 테스트 실행 중 오류: {e}")
        print("경로나 서비스 설정을 다시 확인해주세요.")

if __name__ == "__main__":
    asyncio.run(main())