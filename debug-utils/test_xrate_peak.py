"""
XRATE 파일 Peak NPS 확인
"""
from bms_parser import BMSParser
import new_calc

# XRATE 파일 테스트
test_file = r'd:\계산기\문제분석용\#Time files [06 XRATE].bml'

print("=" * 60)
print("XRATE 파일 Peak NPS 테스트")
print("=" * 60)
print()

# Parse
parser = BMSParser(test_file)
notes = parser.parse()

# 곡 길이 계산
if notes:
    first_time = notes[0]['time']
    last_time = notes[-1]['time']
    duration = last_time - first_time
    if duration < 1.0:
        duration = 1.0
else:
    duration = 0

print(f"파일: #Time files [06 XRATE].bml")
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

# Peak NPS를 1초당으로 환산 (참고용)
peak_per_second = peak_value  # ±500ms = 1초 구간이므로 그대로 사용
print(f"Peak NPS (1초당 환산): {peak_per_second}개/초")
print()

if peak_value == 100:
    print("✅ Peak NPS = 100 확인!")
else:
    print(f"⚠️ Peak NPS = {peak_value} (예상: 100)")

print()
print("=" * 60)
print("✅ XRATE Peak NPS 테스트 완료!")
print("=" * 60)
