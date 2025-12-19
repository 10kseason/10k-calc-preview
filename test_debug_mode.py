"""
디버그 모드 테스트 스크립트
GUI의 디버그 모드에서 출력될 정보를 미리 확인
"""
import numpy as np
from bms_parser import BMSParser
from osu_parser import OsuParser
import metric_calc
import os

def test_debug_output(filepath):
    """디버그 모드 출력 테스트"""
    
    # Parse file
    if filepath.lower().endswith('.osu'):
        parser = OsuParser(filepath)
        notes = parser.parse()
        duration = parser.duration
    else:
        parser = BMSParser(filepath)
        notes = parser.parse()
        duration = notes[-1]['time'] - notes[0]['time'] if notes else 0
        if duration < 1.0:
            duration = 1.0
    
    # Calculate metrics
    metrics = metric_calc.calculate_metrics(notes, duration)
    
    print("=" * 60)
    print("🔧 디버그 모드 출력 예시")
    print("=" * 60)
    print()
    
    # Note type distribution
    note_types = {}
    for note in notes:
        note_type = note.get('type', 'unknown')
        note_types[note_type] = note_types.get(note_type, 0) + 1
    
    print("📝 노트 타입 분포")
    print("─" * 50)
    for ntype, count in sorted(note_types.items()):
        percentage = (count / len(notes) * 100) if notes else 0
        print(f"  {ntype:15s}: {count:5,d}개 ({percentage:5.2f}%)")
    print()
    
    # Metrics statistics
    print("📊 Metrics 통계")
    print("─" * 50)
    metric_names = ['nps', 'ln_strain', 'jack_pen', 'roll_pen', 'alt_cost', 'hand_strain', 'chord_strain']
    for metric_name in metric_names:
        if metric_name in metrics:
            metric_values = metrics[metric_name]
            print(f"\n  {metric_name}:")
            print(f"    최소값    : {np.min(metric_values):.4f}")
            print(f"    최대값    : {np.max(metric_values):.4f}")
            print(f"    평균      : {np.mean(metric_values):.4f}")
            print(f"    중앙값    : {np.median(metric_values):.4f}")
            print(f"    표준편차  : {np.std(metric_values):.4f}")
    print()
    
    # Window details (first 10)
    print("🔍 윈도우별 상세 (처음 10개)")
    print("─" * 50)
    print(f"{'Win':>4s} {'NPS':>6s} {'LN':>6s} {'Jack':>6s} {'Roll':>6s} {'Alt':>6s} {'Hand':>6s} {'Chord':>6s}")
    print("─" * 50)
    for i in range(min(10, len(metrics['nps']))):
        print(f"{i:4d} ", end="")
        print(f"{metrics['nps'][i]:6.2f} ", end="")
        print(f"{metrics['ln_strain'][i]:6.2f} ", end="")
        print(f"{metrics['jack_pen'][i]:6.2f} ", end="")
        print(f"{metrics['roll_pen'][i]:6.2f} ", end="")
        print(f"{metrics['alt_cost'][i]:6.2f} ", end="")
        print(f"{metrics['hand_strain'][i]:6.2f} ", end="")
        print(f"{metrics['chord_strain'][i]:6.2f}")
    print()
    
    # Parser info
    print("📄 파서 상세 정보")
    print("─" * 50)
    if hasattr(parser, 'header'):
        print("  헤더 정보:")
        for key, value in list(parser.header.items())[:10]:
            print(f"    {key}: {value}")
    if hasattr(parser, 'bpm_definitions') and parser.bpm_definitions:
        print(f"\n  BPM 정의: {len(parser.bpm_definitions)}개")
        for bpm_key, bpm_val in list(parser.bpm_definitions.items())[:5]:
            print(f"    {bpm_key}: {bpm_val}")
    print()

if __name__ == '__main__':
    test_file = r'd:\계산기\문제분석용\Collection - Piano Beatmap Set (CircusGalop) [10K HELL CIRCUS].osu'
    
    print("\n디버그 모드 테스트 시작...\n")
    test_debug_output(test_file)
    
    print("=" * 60)
    print("✅ 디버그 모드 출력 테스트 완료!")
    print("=" * 60)
