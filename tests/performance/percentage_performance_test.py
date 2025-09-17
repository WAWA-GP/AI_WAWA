"""
AI 언어학습 앱 기능별 성능 점수(%) 측정 시스템
각 기능의 성능을 0-100% 점수로 환산하여 평가
"""

import asyncio
import aiohttp
import time
import statistics
import psutil
import os
import json
import numpy as np
from datetime import datetime
from dataclasses import dataclass
from typing import Dict, List, Tuple

@dataclass
class PerformanceScore:
    """성능 점수 데이터 클래스"""
    feature_name: str
    score: float  # 0-100%
    details: Dict
    status: str  # "우수", "양호", "보통", "개선필요"

class PerformanceScorer:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.scores = {}
        
        # 성능 기준값 정의 (이상적인 값들)
        self.benchmarks = {
            "api_response_time_ms": {"excellent": 50, "good": 150, "fair": 300, "poor": 500},
            "concurrent_users_success_rate": {"excellent": 95, "good": 85, "fair": 70, "poor": 50},
            "memory_usage_mb": {"excellent": 100, "good": 250, "fair": 500, "poor": 1000},
            "conversation_flow_time_s": {"excellent": 2.0, "good": 4.0, "fair": 7.0, "poor": 10.0},
            "level_test_time_s": {"excellent": 1.5, "good": 3.0, "fair": 5.0, "poor": 8.0},
            "database_query_ms": {"excellent": 50, "good": 200, "fair": 500, "poor": 1000},
            "cpu_usage_percent": {"excellent": 20, "good": 50, "fair": 70, "poor": 90}
        }
    
    def calculate_performance_score(self, actual_value: float, benchmark_key: str, lower_is_better: bool = True) -> float:
        """실제 값과 벤치마크를 비교하여 0-100% 점수 계산"""
        benchmark = self.benchmarks[benchmark_key]
        
        if lower_is_better:
            # 값이 낮을수록 좋은 경우 (응답시간, 메모리 사용량 등)
            if actual_value <= benchmark["excellent"]:
                return 100.0
            elif actual_value <= benchmark["good"]:
                # excellent와 good 사이의 선형 보간
                ratio = (actual_value - benchmark["excellent"]) / (benchmark["good"] - benchmark["excellent"])
                return 100.0 - (ratio * 15.0)  # 100% -> 85%
            elif actual_value <= benchmark["fair"]:
                ratio = (actual_value - benchmark["good"]) / (benchmark["fair"] - benchmark["good"])
                return 85.0 - (ratio * 15.0)  # 85% -> 70%
            elif actual_value <= benchmark["poor"]:
                ratio = (actual_value - benchmark["fair"]) / (benchmark["poor"] - benchmark["fair"])
                return 70.0 - (ratio * 20.0)  # 70% -> 50%
            else:
                # poor 기준보다 나쁜 경우
                excess_ratio = min((actual_value - benchmark["poor"]) / benchmark["poor"], 1.0)
                return max(50.0 - (excess_ratio * 50.0), 0.0)  # 50% -> 0%
        else:
            # 값이 높을수록 좋은 경우 (성공률 등)
            if actual_value >= benchmark["excellent"]:
                return 100.0
            elif actual_value >= benchmark["good"]:
                ratio = (actual_value - benchmark["good"]) / (benchmark["excellent"] - benchmark["good"])
                return 85.0 + (ratio * 15.0)  # 85% -> 100%
            elif actual_value >= benchmark["fair"]:
                ratio = (actual_value - benchmark["fair"]) / (benchmark["good"] - benchmark["fair"])
                return 70.0 + (ratio * 15.0)  # 70% -> 85%
            elif actual_value >= benchmark["poor"]:
                ratio = (actual_value - benchmark["poor"]) / (benchmark["fair"] - benchmark["poor"])
                return 50.0 + (ratio * 20.0)  # 50% -> 70%
            else:
                # poor 기준보다 나쁜 경우
                ratio = min(actual_value / benchmark["poor"], 1.0)
                return ratio * 50.0  # 0% -> 50%
    
    def get_status_from_score(self, score: float) -> str:
        """점수에 따른 상태 문자열 반환"""
        if score >= 85:
            return "우수"
        elif score >= 70:
            return "양호"
        elif score >= 50:
            return "보통"
        else:
            return "개선필요"
    
    async def test_api_performance(self) -> PerformanceScore:
        """API 성능 테스트 (0-100% 점수)"""
        print("🔌 API 성능 테스트 중...")
        
        endpoints = [
            ("/", "GET"),
            ("/health", "GET"),
            ("/api/situations", "GET"),
            ("/api/languages", "GET")
        ]
        
        all_times = []
        endpoint_details = {}
        
        async with aiohttp.ClientSession() as session:
            for endpoint, method in endpoints:
                times = []
                
                for _ in range(10):
                    start_time = time.time()
                    try:
                        async with session.get(f"{self.base_url}{endpoint}") as resp:
                            await resp.json()
                        end_time = time.time()
                        times.append((end_time - start_time) * 1000)
                    except Exception as e:
                        times.append(5000)  # 실패시 5초로 처리
                
                avg_time = statistics.mean(times)
                all_times.extend(times)
                endpoint_details[endpoint] = avg_time
        
        overall_avg = statistics.mean(all_times)
        score = self.calculate_performance_score(overall_avg, "api_response_time_ms", lower_is_better=True)
        
        return PerformanceScore(
            feature_name="API 응답성",
            score=round(score, 1),
            details={
                "avg_response_time_ms": round(overall_avg, 2),
                "endpoint_details": {k: round(v, 2) for k, v in endpoint_details.items()},
                "benchmark": self.benchmarks["api_response_time_ms"]
            },
            status=self.get_status_from_score(score)
        )
    
    async def test_concurrent_users_performance(self) -> PerformanceScore:
        """동시 사용자 처리 성능 테스트"""
        print("👥 동시 사용자 처리 성능 테스트 중...")
        
        user_counts = [10, 50, 100]
        success_rates = []
        
        for user_count in user_counts:
            async with aiohttp.ClientSession() as session:
                tasks = []
                
                for i in range(user_count):
                    task = self.simulate_simple_request(session, f"concurrent_test_{i}")
                    tasks.append(task)
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                successful = sum(1 for r in results if not isinstance(r, Exception))
                success_rate = (successful / user_count) * 100
                success_rates.append(success_rate)
        
        # 가장 까다로운 조건(100명)의 성공률을 기준으로 점수 계산
        critical_success_rate = success_rates[-1] if success_rates else 0
        score = self.calculate_performance_score(critical_success_rate, "concurrent_users_success_rate", lower_is_better=False)
        
        return PerformanceScore(
            feature_name="동시 사용자 처리",
            score=round(score, 1),
            details={
                "success_rates_by_users": dict(zip(user_counts, [round(sr, 1) for sr in success_rates])),
                "critical_success_rate": round(critical_success_rate, 1),
                "benchmark": self.benchmarks["concurrent_users_success_rate"]
            },
            status=self.get_status_from_score(score)
        )
    
    async def simulate_simple_request(self, session, user_id):
        """간단한 요청 시뮬레이션"""
        try:
            async with session.get(f"{self.base_url}/health") as resp:
                if resp.status == 200:
                    return "성공"
                else:
                    raise Exception(f"HTTP {resp.status}")
        except Exception as e:
            return e
    
    async def test_conversation_flow_performance(self) -> PerformanceScore:
        """대화 플로우 성능 테스트"""
        print("💬 대화 플로우 성능 테스트 중...")
        
        flow_times = []
        
        async with aiohttp.ClientSession() as session:
            for i in range(5):  # 5번 테스트
                start_time = time.time()
                
                try:
                    # 대화 시작
                    start_data = {
                        "user_id": f"flow_test_{i}",
                        "situation": "restaurant",
                        "difficulty": "intermediate",
                        "language": "en"
                    }
                    
                    async with session.post(f"{self.base_url}/api/conversation/start", 
                                          json=start_data) as resp:
                        if resp.status == 200:
                            result = await resp.json()
                            session_id = result["data"]["session_id"]
                            
                            # 간단한 메시지 전송
                            message_data = {
                                "session_id": session_id,
                                "message": "Hello",
                                "language": "en"
                            }
                            
                            async with session.post(f"{self.base_url}/api/conversation/text", 
                                                  json=message_data) as msg_resp:
                                await msg_resp.json()
                    
                    end_time = time.time()
                    flow_times.append(end_time - start_time)
                    
                except Exception as e:
                    flow_times.append(10.0)  # 실패시 10초로 처리
        
        avg_time = statistics.mean(flow_times)
        score = self.calculate_performance_score(avg_time, "conversation_flow_time_s", lower_is_better=True)
        
        return PerformanceScore(
            feature_name="대화 플로우",
            score=round(score, 1),
            details={
                "avg_flow_time_s": round(avg_time, 2),
                "min_time_s": round(min(flow_times), 2),
                "max_time_s": round(max(flow_times), 2),
                "benchmark": self.benchmarks["conversation_flow_time_s"]
            },
            status=self.get_status_from_score(score)
        )
    
    async def test_level_test_performance(self) -> PerformanceScore:
        """레벨 테스트 성능"""
        print("📝 레벨 테스트 성능 테스트 중...")
        
        test_times = []
        
        async with aiohttp.ClientSession() as session:
            for i in range(3):  # 3번 테스트
                start_time = time.time()
                
                try:
                    # 레벨 테스트 시작
                    start_data = {
                        "user_id": f"level_test_{i}",
                        "language": "english"
                    }
                    
                    async with session.post(f"{self.base_url}/api/level-test/start", 
                                          json=start_data) as resp:
                        if resp.status == 200:
                            result = await resp.json()
                            session_id = result["session_id"]
                            
                            # 3개 문제 답변
                            for q in range(3):
                                answer_data = {
                                    "session_id": session_id,
                                    "question_id": f"test_q_{q}",
                                    "answer": "A"
                                }
                                
                                async with session.post(f"{self.base_url}/api/level-test/answer", 
                                                      json=answer_data) as answer_resp:
                                    await answer_resp.json()
                    
                    end_time = time.time()
                    test_times.append(end_time - start_time)
                    
                except Exception as e:
                    test_times.append(8.0)  # 실패시 8초로 처리
        
        avg_time = statistics.mean(test_times) if test_times else 8.0
        score = self.calculate_performance_score(avg_time, "level_test_time_s", lower_is_better=True)
        
        return PerformanceScore(
            feature_name="레벨 테스트",
            score=round(score, 1),
            details={
                "avg_test_time_s": round(avg_time, 2),
                "questions_per_second": round(3 / avg_time, 2),
                "benchmark": self.benchmarks["level_test_time_s"]
            },
            status=self.get_status_from_score(score)
        )
    
    def test_system_resources_performance(self) -> PerformanceScore:
        """시스템 리소스 성능 테스트"""
        print("💾 시스템 리소스 성능 테스트 중...")
        
        process = psutil.Process(os.getpid())
        memory_mb = process.memory_info().rss / 1024 / 1024
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # 메모리와 CPU 점수를 각각 계산 후 평균
        memory_score = self.calculate_performance_score(memory_mb, "memory_usage_mb", lower_is_better=True)
        cpu_score = self.calculate_performance_score(cpu_percent, "cpu_usage_percent", lower_is_better=True)
        
        overall_score = (memory_score + cpu_score) / 2
        
        return PerformanceScore(
            feature_name="시스템 리소스",
            score=round(overall_score, 1),
            details={
                "memory_usage_mb": round(memory_mb, 2),
                "cpu_usage_percent": round(cpu_percent, 1),
                "memory_score": round(memory_score, 1),
                "cpu_score": round(cpu_score, 1),
                "memory_benchmark": self.benchmarks["memory_usage_mb"],
                "cpu_benchmark": self.benchmarks["cpu_usage_percent"]
            },
            status=self.get_status_from_score(overall_score)
        )
    
    async def test_database_performance(self) -> PerformanceScore:
        """데이터베이스 성능 테스트 (시뮬레이션)"""
        print("🗄️ 데이터베이스 성능 테스트 중...")
        
        # 실제 DB 쿼리 대신 통계 API 호출로 테스트
        query_times = []
        
        async with aiohttp.ClientSession() as session:
            for _ in range(5):
                start_time = time.time()
                
                try:
                    async with session.get(f"{self.base_url}/api/data/statistics") as resp:
                        await resp.json()
                    end_time = time.time()
                    query_times.append((end_time - start_time) * 1000)
                except Exception as e:
                    query_times.append(1000)  # 실패시 1초로 처리
        
        avg_query_time = statistics.mean(query_times)
        score = self.calculate_performance_score(avg_query_time, "database_query_ms", lower_is_better=True)
        
        return PerformanceScore(
            feature_name="데이터베이스",
            score=round(score, 1),
            details={
                "avg_query_time_ms": round(avg_query_time, 2),
                "min_query_time_ms": round(min(query_times), 2),
                "max_query_time_ms": round(max(query_times), 2),
                "benchmark": self.benchmarks["database_query_ms"]
            },
            status=self.get_status_from_score(score)
        )
    
    async def run_all_performance_tests(self) -> Dict[str, PerformanceScore]:
        """모든 성능 테스트 실행 및 점수 계산"""
        print("🚀 AI 언어학습 앱 성능 점수 측정 시작")
        print("=" * 60)
        
        # 각 기능별 성능 테스트 실행
        tests = [
            self.test_api_performance(),
            self.test_concurrent_users_performance(),
            self.test_conversation_flow_performance(),
            self.test_level_test_performance(),
            self.test_database_performance()
        ]
        
        results = await asyncio.gather(*tests)
        
        # 시스템 리소스 테스트 (동기)
        system_result = self.test_system_resources_performance()
        results.append(system_result)
        
        # 결과 정리
        scores = {}
        for result in results:
            scores[result.feature_name] = result
        
        return scores
    
    def generate_score_report(self, scores: Dict[str, PerformanceScore]):
        """성능 점수 리포트 생성"""
        print("\n" + "=" * 60)
        print("📊 기능별 성능 점수 결과")
        print("=" * 60)
        
        total_score = 0
        feature_count = len(scores)
        
        for feature_name, score_data in scores.items():
            score = score_data.score
            status = score_data.status
            total_score += score
            
            # 점수에 따른 시각적 표시
            bar_length = 20
            filled_length = int(bar_length * score / 100)
            bar = "█" * filled_length + "░" * (bar_length - filled_length)
            
            print(f"  {feature_name:<15} │{bar}│ {score:5.1f}% ({status})")
        
        # 전체 평균 점수
        overall_score = total_score / feature_count
        overall_status = self.get_status_from_score(overall_score)
        
        print("─" * 60)
        overall_bar_length = 30
        overall_filled = int(overall_bar_length * overall_score / 100)
        overall_bar = "█" * overall_filled + "░" * (overall_bar_length - overall_filled)
        
        print(f"  전체 평균 점수    │{overall_bar}│ {overall_score:5.1f}% ({overall_status})")
        print("=" * 60)
        
        # 상세 정보 표시
        print(f"\n📋 상세 성능 분석:")
        for feature_name, score_data in scores.items():
            if score_data.score < 70:  # 70% 미만인 기능들에 대한 개선 제안
                print(f"  ⚠️  {feature_name}: {score_data.score}% - 개선 권장")
                
                # 개선 제안
                if "api" in feature_name.lower():
                    print(f"     💡 캐싱, DB 쿼리 최적화, 코드 프로파일링 권장")
                elif "동시" in feature_name:
                    print(f"     💡 비동기 처리 최적화, 커넥션 풀 조정 권장")
                elif "메모리" in score_data.details:
                    memory_mb = score_data.details.get("memory_usage_mb", 0)
                    if memory_mb > 500:
                        print(f"     💡 메모리 누수 확인, 가비지 컬렉션 최적화 권장")
        
        # JSON 리포트 저장
        report_data = {
            "timestamp": datetime.now().isoformat(),
            "overall_score": round(overall_score, 1),
            "overall_status": overall_status,
            "feature_scores": {
                name: {
                    "score": data.score,
                    "status": data.status,
                    "details": data.details
                }
                for name, data in scores.items()
            }
        }
        
        report_file = f"performance_scores_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n📄 상세 점수 리포트 저장됨: {report_file}")
        print(f"✅ 성능 측정 완료! 전체 점수: {overall_score:.1f}%")

async def main():
    """메인 실행 함수"""
    scorer = PerformanceScorer()
    scores = await scorer.run_all_performance_tests()
    scorer.generate_score_report(scores)

if __name__ == "__main__":
    asyncio.run(main())