"""
BMS vs OSU NPS 비교 테스트
같은 패턴의 BMS와 OSU 파일을 비교하여 NPS 계산 일관성 확인
"""
from bms_parser import BMSParser
from osu_parser import OsuParser
import new_calc

# 파일 경로
bms_file = r'D:\계산기\문제분석용\t테스트\Collection - Piano Beatmap Set (CircusGalop) [10K HELL CIRCUS].bms'
osu_file = r'D:\계산기\문제분석용\t테스트\Collection - Piano Beatmap Set (CircusGalop) [10K HELL CIRCUS].osu'

print('='*70)
print('BMS vs OSU NPS 비교 테스트')
print('='*70)
print()

# BMS 파싱
bms_parser = BMSParser(bms_file)
bms_notes = bms_parser.parse()
bms_duration = bms_parser.duration

# OSU 파싱
osu_parser = OsuParser(osu_file)
osu_notes = osu_parser.parse()
osu_duration = osu_parser.duration

print(f'BMS: 노트수={len(bms_notes):,}, 길이={bms_duration:.3f}초')
print(f'OSU: 노트수={len(osu_notes):,}, 길이={osu_duration:.3f}초')
print()

# NPS 메트릭 계산
bms_metrics = new_calc.calculate_nps_metrics(bms_notes, bms_duration)
osu_metrics = new_calc.calculate_nps_metrics(osu_notes, osu_duration)

print('NPS 비교:')
print(f"  Global NPS - BMS: {bms_metrics['global_nps']}, OSU: {osu_metrics['global_nps']}")
print(f"  Peak NPS   - BMS: {bms_metrics['peak_nps']}, OSU: {osu_metrics['peak_nps']}")
print(f"  NPS Std    - BMS: {bms_metrics['nps_std']}, OSU: {osu_metrics['nps_std']}")
print()

# 차이 확인
peak_diff = abs(bms_metrics['peak_nps'] - osu_metrics['peak_nps'])
global_diff = abs(bms_metrics['global_nps'] - osu_metrics['global_nps'])
std_diff = abs(bms_metrics['nps_std'] - osu_metrics['nps_std'])

print('차이 분석:')
print(f"  Global NPS 차이: {global_diff:.4f}")
print(f"  Peak NPS 차이: {peak_diff}")
print(f"  NPS Std 차이: {std_diff:.4f}")
print()

if peak_diff == 0:
    print('✅ Peak NPS 동일!')
else:
    print(f'⚠️ Peak NPS 차이 발생: {peak_diff}')

print()
print('='*70)
print('테스트 완료')
print('='*70)
