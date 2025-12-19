"""
로컬 NPS (±500ms) 계산 테스트
"""
from bms_parser import BMSParser
from osu_parser import OsuParser
import new_calc

# CircusGalop 테스트
test_file = r'd:\계산기\문제분석용\Collection - Piano Beatmap Set (CircusGalop) [10K HELL CIRCUS].osu'

print("=" * 60)
print("로컬 NPS (±500ms) 계산 테스트")
print("=" * 60)
print()

# Parse
parser = OsuParser(test_file)
notes = parser.parse()
duration = parser.duration

print(f"파일: CircusGalop [10K HELL CIRCUS]")
print(f"총 노트수: {len(notes):,}개")
print(f"곡 길이: {duration:.2f}초")
print()

# NPS 메트릭 계산
metrics = new_calc.calculate_nps_metrics(notes, duration)

print("=" * 60)
print("NPS 메트릭 결과")
print("=" * 60)
print(f"Global NPS (총 노트수 / 곡 길이): {metrics['global_nps']}")
print(f"Peak NPS   (±500ms 최대 밀도):    {metrics['peak_nps']}개")
print(f"NPS 표준편차 (변동성):            {metrics['nps_std']}")
print()

# 로컬 NPS 분포 확인 (처음 10개 노트)
print("=" * 60)
print("로컬 NPS 상세 (처음 10개 노트)")
print("=" * 60)
print(f"{'노트#':>6s} {'시간(초)':>10s} {'로컬NPS':>10s}")
print("-" * 60)

for i, note in enumerate(notes[:10]):
    t = round(note['time'], 3)  # ms 단위로 반올림
    # 부동소수점 오차 방지: t+0.5 대신 t+0.499999999999 사용 후 <= 비교
    window_start = t - 0.5
    window_end = t + 0.499999999999
    count = sum(1 for n in notes if window_start <= n['time'] <= window_end)
    print(f"{i+1:6d} {t:10.3f} {count:10d}개")

print()

# Peak 발생 지점 찾기
local_nps_all = []
for note in notes:
    t = round(note['time'], 3)  # ms 단위로 반올림
    # 부동소수점 오차 방지: t+0.5 대신 t+0.499999999999 사용 후 <= 비교
    window_start = t - 0.5
    window_end = t + 0.499999999999
    count = sum(1 for n in notes if window_start <= n['time'] <= window_end)
    local_nps_all.append((t, count))

# Peak NPS 발생 시점
peak_time, peak_value = max(local_nps_all, key=lambda x: x[1])

print("=" * 60)
print(f"Peak NPS 발생 시점")
print("=" * 60)
print(f"시간: {peak_time:.3f}초 ({peak_time/60:.2f}분)")
print(f"밀도: {peak_value}개 (±500ms 구간 내)")
print()

print("=" * 60)
print("✅ 로컬 NPS 계산 테스트 완료!")
print("=" * 60)
