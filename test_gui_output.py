"""
GUI 출력 형식 테스트 스크립트
새로운 NPS 표시 및 UI 개선 사항을 콘솔에서 미리 확인
"""
import numpy as np
from bms_parser import BMSParser
from osu_parser import OsuParser
import metric_calc
import calc
import os

def test_gui_output(filepath):
    """GUI와 동일한 형식으로 출력 테스트"""
    
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
    
    # Calculate NPS statistics
    global_nps = len(notes) / duration
    avg_nps = np.mean(metrics['nps'])
    peak_nps = np.max(metrics['nps'])
    nps_std = np.std(metrics['nps'])
    
    # Get key count
    key_count = parser.key_count if hasattr(parser, 'key_count') else '?'
    
    # Build result string (same as GUI)
    res_str = "═" * 50 + "\n"
    res_str += f"📁 파일: {os.path.basename(filepath)}\n"
    res_str += f"🎹 키모드: {key_count}K\n"
    res_str += "═" * 50 + "\n\n"
    
    res_str += "📊 기본 지표\n"
    res_str += "─" * 50 + "\n"
    res_str += f"  총 노트수      : {len(notes):,}개\n"
    res_str += f"  곡 길이        : {duration:.2f}초 ({duration/60:.2f}분)\n"
    res_str += f"  Global NPS     : {global_nps:.2f}\n"
    res_str += f"  평균 NPS       : {avg_nps:.2f}\n"
    res_str += f"  Peak NPS       : {peak_nps:.2f}\n"
    res_str += f"  NPS 표준편차   : {nps_std:.2f}\n\n"
    
    res_str += "🎯 난이도 분석 (예시)\n"
    res_str += "─" * 50 + "\n"
    res_str += f"  사용 모델      : NPS Linear\n"
    res_str += f"  추정 레벨      : (계산 필요)\n\n"
    
    res_str += "💚 HP9 참고 정보\n"
    res_str += "─" * 50 + "\n"
    res_str += f"  최대 허용 미스 : ~예시\n"
    res_str += "  (나머지 모두 300s 가정)\n"
    
    print(res_str)

if __name__ == '__main__':
    # Test with CircusGalop
    test_file = r'd:\계산기\문제분석용\Collection - Piano Beatmap Set (CircusGalop) [10K HELL CIRCUS].osu'
    
    print("=" * 60)
    print("GUI 출력 형식 테스트")
    print("=" * 60)
    print()
    
    test_gui_output(test_file)
    
    print("\n" + "=" * 60)
    print("✅ 새로운 GUI 형식 테스트 완료!")
    print("=" * 60)
