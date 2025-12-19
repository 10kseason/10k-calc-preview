"""
BMS vs OSU NPS 표준편차 차이 심층 분석
1초 윈도우별 NPS 분포를 비교하여 차이 원인 분석
"""
from bms_parser import BMSParser
from osu_parser import OsuParser
import numpy as np

# 파일 경로
bms_file = r'D:\계산기\문제분석용\t테스트\bof_10K.bms'
osu_file = r'D:\계산기\문제분석용\t테스트\sentire - Takigyou Lv28 (XDerbyX) [lv.15  [10K BOSS]].osu'

print('='*70)
print('NPS 표준편차 차이 심층 분석')
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

# 1초 윈도우별 NPS 계산
def calc_window_nps(notes, duration):
    window_nps = []
    for t in range(int(duration) + 1):
        count = sum(1 for n in notes if t <= n['time'] < t + 1)
        window_nps.append(count)
    return window_nps

bms_window_nps = calc_window_nps(bms_notes, bms_duration)
osu_window_nps = calc_window_nps(osu_notes, osu_duration)

print(f'BMS 윈도우 개수: {len(bms_window_nps)}')
print(f'OSU 윈도우 개수: {len(osu_window_nps)}')
print()

# 표준편차 계산
bms_std = np.std(bms_window_nps)
osu_std = np.std(osu_window_nps)
print(f'BMS NPS 표준편차: {bms_std:.4f}')
print(f'OSU NPS 표준편차: {osu_std:.4f}')
print(f'차이: {abs(bms_std - osu_std):.4f}')
print()

# 윈도우별 차이 분석
print('='*70)
print('윈도우별 NPS 차이 분석')
print('='*70)

diff_windows = []
for i in range(min(len(bms_window_nps), len(osu_window_nps))):
    diff = bms_window_nps[i] - osu_window_nps[i]
    if diff != 0:
        diff_windows.append((i, bms_window_nps[i], osu_window_nps[i], diff))

print(f'차이가 있는 윈도우 개수: {len(diff_windows)}')
print()

if diff_windows:
    print('차이가 있는 윈도우 상세:')
    print(f'{"윈도우(초)":<12} {"BMS":<8} {"OSU":<8} {"차이":<8}')
    print('-'*40)
    for t, bms_val, osu_val, diff in diff_windows[:20]:  # 최대 20개 출력
        print(f'{t:<12} {bms_val:<8} {osu_val:<8} {diff:<+8}')
    if len(diff_windows) > 20:
        print(f'... 외 {len(diff_windows) - 20}개 더')
    print()

# 노트 시간 경계 분석 (1초 경계 주변 노트들)
print('='*70)
print('1초 경계 주변 노트 시간 분석')
print('='*70)

for window_idx, bms_val, osu_val, diff in diff_windows[:5]:
    print(f'\n--- 윈도우 {window_idx}초~{window_idx+1}초 ---')
    
    # BMS 경계 노트
    bms_boundary = [n['time'] for n in bms_notes 
                   if window_idx - 0.01 <= n['time'] <= window_idx + 0.01 
                   or window_idx + 1 - 0.01 <= n['time'] <= window_idx + 1 + 0.01]
    
    # OSU 경계 노트
    osu_boundary = [n['time'] for n in osu_notes 
                   if window_idx - 0.01 <= n['time'] <= window_idx + 0.01 
                   or window_idx + 1 - 0.01 <= n['time'] <= window_idx + 1 + 0.01]
    
    print(f'BMS 경계 노트 시간: {bms_boundary}')
    print(f'OSU 경계 노트 시간: {osu_boundary}')
    
    # 해당 윈도우 내 노트 시간 분포
    bms_in_window = sorted([n['time'] for n in bms_notes if window_idx <= n['time'] < window_idx + 1])
    osu_in_window = sorted([n['time'] for n in osu_notes if window_idx <= n['time'] < window_idx + 1])
    
    print(f'BMS 윈도우 내 노트수: {len(bms_in_window)}')
    print(f'OSU 윈도우 내 노트수: {len(osu_in_window)}')
    
    # 차이나는 노트 시간 찾기
    bms_set = set(round(t, 4) for t in bms_in_window)
    osu_set = set(round(t, 4) for t in osu_in_window)
    
    only_bms = bms_set - osu_set
    only_osu = osu_set - bms_set
    
    if only_bms:
        print(f'BMS에만 있는 시간: {sorted(only_bms)}')
    if only_osu:
        print(f'OSU에만 있는 시간: {sorted(only_osu)}')

print()
print('='*70)
print('노트 시간 정밀 비교 (처음 100개)')
print('='*70)

# 처음 100개 노트 시간 비교
for i in range(min(100, len(bms_notes), len(osu_notes))):
    bms_t = bms_notes[i]['time']
    osu_t = osu_notes[i]['time']
    diff = abs(bms_t - osu_t)
    if diff > 0.0001:  # 0.1ms 이상 차이
        print(f'노트 {i}: BMS={bms_t:.6f}, OSU={osu_t:.6f}, 차이={diff:.6f}초 ({diff*1000:.3f}ms)')

print()
print('='*70)
print('분석 완료')
print('='*70)
