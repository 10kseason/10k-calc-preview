"""
debug_osu_export.py - 디버그용 OSU 파일 생성

각 노트의 메트릭 값을 키음 이름으로 표시하여 오스 에디터에서 시각적으로 확인 가능
예: n12 (NPS=12), f24.50 (flex=24.50), j16 (jack=16)
"""

import os
import numpy as np
from datetime import datetime


def calculate_note_metrics(notes, metrics):
    """
    각 노트별 메트릭 계산
    
    Args:
        notes (list): 노트 리스트
        metrics (dict): metric_calc의 결과
    
    Returns:
        list: 각 노트별 메트릭 딕셔너리 리스트
    """
    note_metrics = []
    
    for i, note in enumerate(notes):
        t = round(note['time'], 3)  # ms 단위로 반올림
        
        # Local NPS (±500ms)
        # 부동소수점 오차 방지: t+0.5 대신 t+0.499999999999 사용 후 <= 비교
        window_start = t - 0.5
        window_end = t + 0.499999999999
        local_nps = sum(1 for n in notes if window_start <= n['time'] <= window_end)
        
        # 해당 시간의 1초 윈도우 메트릭 찾기
        window_idx = int(t)
        if window_idx >= len(metrics['nps']):
            window_idx = len(metrics['nps']) - 1
        
        # 메트릭 추출
        nps_1s = metrics['nps'][window_idx] if window_idx >= 0 else 0
        ln_strain = metrics.get('ln_strain', [0])[window_idx] if window_idx >= 0 else 0
        jack_pen = metrics.get('jack_pen', [0])[window_idx] if window_idx >= 0 else 0
        roll_pen = metrics.get('roll_pen', [0])[window_idx] if window_idx >= 0 else 0
        alt_cost = metrics.get('alt_cost', [0])[window_idx] if window_idx >= 0 else 0
        hand_strain = metrics.get('hand_strain', [0])[window_idx] if window_idx >= 0 else 0
        chord_strain = metrics.get('chord_strain', [0])[window_idx] if window_idx >= 0 else 0
        
        note_metrics.append({
            'note': note,
            'local_nps': local_nps,
            'nps_1s': nps_1s,
            'ln_strain': ln_strain,
            'jack': jack_pen,
            'roll': roll_pen,
            'alt': alt_cost,
            'hand': hand_strain,
            'chord': chord_strain
        })
    
    return note_metrics


def format_hitsound_name(metric_dict, mode='local_nps', note_type='note'):
    """
    메트릭 값을 키음 이름 형식으로 변환
    
    Args:
        metric_dict (dict): 노트 메트릭
        mode (str): 표시할 메트릭 종류
        note_type (str): 노트 타입 ('note', 'ln_start', 'ln_end')
    
    Returns:
        str: 키음 파일명 (예: "n12.wav", "Hn12.wav" (LN 머리), "Tn12.wav" (LN 꼬리))
    """
    # 롱노트 머리/꼬리 접두어
    # H = Head (머리, ln_start)
    # T = Tail (꼬리, ln_end)
    prefix = ''
    if note_type == 'ln_start':
        prefix = 'H'  # Head (머리)
    elif note_type == 'ln_end':
        prefix = 'T'  # Tail (꼬리)
    
    if mode == 'local_nps':
        value = metric_dict['local_nps']
        return f"{prefix}n{value}.wav"
    elif mode == 'jack':
        value = metric_dict['jack']
        formatted = f"{value:.2f}" if value != int(value) else f"{int(value)}"
        return f"{prefix}j{formatted}.wav"
    elif mode == 'chord':
        value = metric_dict['chord']
        return f"{prefix}c{value:.2f}.wav"
    elif mode == 'hand':
        value = metric_dict['hand']
        formatted = f"{value:.2f}" if value != int(value) else f"{int(value)}"
        return f"{prefix}h{formatted}.wav"
    elif mode == 'all':
        # 모든 메트릭을 짧게 표시
        n = metric_dict['local_nps']
        j = metric_dict['jack']
        c = metric_dict['chord']
        return f"{prefix}n{n}_j{j:.0f}_c{c:.1f}.wav"
    else:
        return "normal-hitnormal.wav"


def format_ln_hitsound_name(head_metric, tail_metric, mode='local_nps'):
    """
    롱노트용 키음 이름 생성 - 머리(H)와 꼬리(T) 메트릭 모두 표시
    
    Args:
        head_metric (dict): 롱노트 머리(ln_start) 메트릭
        tail_metric (dict): 롱노트 꼬리(ln_end) 메트릭
        mode (str): 표시할 메트릭 종류
    
    Returns:
        str: 키음 파일명 (예: "Hn12_Tn15.wav" - 머리 NPS=12, 꼬리 NPS=15)
    """
    if mode == 'local_nps':
        h_val = head_metric['local_nps']
        t_val = tail_metric['local_nps']
        return f"Hn{h_val}_Tn{t_val}.wav"
    elif mode == 'jack':
        h_val = head_metric['jack']
        t_val = tail_metric['jack']
        h_fmt = f"{h_val:.0f}" if h_val == int(h_val) else f"{h_val:.1f}"
        t_fmt = f"{t_val:.0f}" if t_val == int(t_val) else f"{t_val:.1f}"
        return f"Hj{h_fmt}_Tj{t_fmt}.wav"
    elif mode == 'chord':
        h_val = head_metric['chord']
        t_val = tail_metric['chord']
        return f"Hc{h_val:.1f}_Tc{t_val:.1f}.wav"
    elif mode == 'hand':
        h_val = head_metric['hand']
        t_val = tail_metric['hand']
        h_fmt = f"{h_val:.0f}" if h_val == int(h_val) else f"{h_val:.1f}"
        t_fmt = f"{t_val:.0f}" if t_val == int(t_val) else f"{t_val:.1f}"
        return f"Hh{h_fmt}_Th{t_fmt}.wav"
    elif mode == 'all':
        # 모든 메트릭 표시 (간략화)
        h_n, h_j, h_c = head_metric['local_nps'], head_metric['jack'], head_metric['chord']
        t_n, t_j, t_c = tail_metric['local_nps'], tail_metric['jack'], tail_metric['chord']
        return f"Hn{h_n}j{h_j:.0f}_Tn{t_n}j{t_j:.0f}.wav"
    else:
        return "normal-hitnormal.wav"


def export_debug_osu(notes, metrics, original_file, output_path, metric_mode='local_nps', key_count=None):
    """
    디버그용 .osu 파일 생성
    
    Args:
        notes (list): 노트 리스트
        metrics (dict): metric_calc 결과
        original_file (str): 원본 파일 경로
        output_path (str): 출력 파일 경로
        metric_mode (str): 표시할 메트릭 모드
        key_count (int): 키 개수 (None이면 노트의 열 번호에서 자동 감지)
    """
    # 노트별 메트릭 계산
    note_metrics = calculate_note_metrics(notes, metrics)
    
    # key_count 자동 감지 (전달되지 않은 경우)
    if key_count is None:
        if notes:
            used_columns = set(n['column'] for n in notes)
            max_col = max(used_columns)
            min_col = min(used_columns)
            # DP: 열 9-16 사용 시 17키
            if max_col >= 9:
                key_count = 17
            # SP: 열 1-8 사용 시 8키
            else:
                key_count = 8
        else:
            key_count = 8  # 기본값
    
    # 원본 파일이 .osu라면 헤더 정보 가져오기
    header_lines = []
    hit_objects_started = False
    
    if original_file.lower().endswith('.osu'):
        try:
            with open(original_file, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    if line.strip() == '[HitObjects]':
                        hit_objects_started = True
                        header_lines.append(line)
                        break
                    header_lines.append(line)
        except:
            # 파일 읽기 실패 시 기본 헤더 사용
            pass
    
    # 헤더가 없으면 기본 헤더 생성
    if not header_lines:
        header_lines = [
            "osu file format v14\n",
            "\n",
            "[General]\n",
            "AudioFilename: virtual\n",
            "AudioLeadIn: 0\n",
            "PreviewTime: 0\n",
            "Countdown: 0\n",
            "SampleSet: Normal\n",
            "StackLeniency: 0.7\n",
            "Mode: 3\n",
            "LetterboxInBreaks: 0\n",
            "\n",
            "[Difficulty]\n",
            "HPDrainRate: 8\n",
            f"CircleSize: {key_count}\n",  # 키 개수에 맞게 동적 설정
            "OverallDifficulty: 8\n",
            "ApproachRate: 5\n",
            "SliderMultiplier: 1.4\n",
            "SliderTickRate: 1\n",
            "\n",
            "[Metadata]\n",
            f"Title:Debug View - {metric_mode}\n",
            "TitleUnicode:Debug View\n",
            f"Artist:Metric: {metric_mode}\n",
            "ArtistUnicode:Debug\n",
            "Creator:Debug Tool\n",
            f"Version:Debug-{metric_mode}\n",
            "Source:\n",
            "Tags:debug metrics visualization\n",
            "\n",
            "[HitObjects]\n"
        ]
    
    # .osu 파일 작성
    with open(output_path, 'w', encoding='utf-8') as f:
        # 헤더 쓰기
        f.writelines(header_lines)
        
        # HitObjects 쓰기
        for i, nm in enumerate(note_metrics):
            note = nm['note']
            
            # 열(column) 가져오기
            column = note.get('column', 1)
            
            # x 좌표 계산: key_count에 맞게 변환
            # OSU 공식: column = floor(x * key_count / 512)
            # 역산: x = (col_0indexed + 0.5) * 512 / key_count
            #
            # 모든 키 모드에서 열이 1부터 시작하므로 1을 빼서 0-indexed로 변환
            # (BMS 파서의 모든 키 모드 매핑이 열 1부터 시작함)
            col_0indexed = column - 1
            
            # 음수 방지 (혹시 열 0이 있는 경우)
            if col_0indexed < 0:
                col_0indexed = 0
            
            # x 좌표 계산
            x = int((col_0indexed + 0.5) * 512 / key_count)
            y = 192  # 고정
            
            # 시간 (ms)
            time_ms = int(note['time'] * 1000)
            
            # 노트 타입
            note_type = note.get('type', 'note')
            
            # HitSound 파일명 생성 (롱노트 머리/꼬리 표시 포함)
            hitsound = format_hitsound_name(nm, metric_mode, note_type)
            
            if note_type == 'ln_start':
                # Long Note: x,y,time,type,hitSound,endTime:hitSample
                # 다음 ln_end 찾기 + 꼬리 메트릭도 가져오기
                end_time = time_ms + 100  # 기본값
                tail_metric = nm  # 기본값: 머리와 동일
                for j in range(i+1, len(note_metrics)):
                    next_note = note_metrics[j]['note']
                    if (next_note.get('type') == 'ln_end' and 
                        next_note.get('column') == note.get('column')):
                        end_time = int(next_note['time'] * 1000)
                        tail_metric = note_metrics[j]  # 꼬리 메트릭 저장
                        break
                
                # 머리 + 꼬리 메트릭 모두 표시하는 키음 이름 생성
                hitsound = format_ln_hitsound_name(nm, tail_metric, metric_mode)
                
                type_flags = 128  # LN
                f.write(f"{x},{y},{time_ms},{type_flags},0,{end_time}:0:0:0:0:{hitsound}\n")
            
            elif note_type == 'ln_end':
                # LN end는 이미 start에서 처리됨
                continue
            
            else:
                # Normal Note
                type_flags = 1  # Circle
                f.write(f"{x},{y},{time_ms},{type_flags},0,0:0:0:0:{hitsound}\n")
    
    print(f"✅ 디버그 OSU 파일 생성: {output_path}")
    print(f"   메트릭 모드: {metric_mode}, 키 개수: {key_count}")
    print(f"   총 노트수: {len([n for n in notes if n.get('type') != 'ln_end'])}")


def export_multiple_modes(notes, metrics, original_file, output_dir, key_count=None):
    """
    여러 메트릭 모드로 여러 파일 생성
    
    Args:
        notes (list): 노트 리스트
        metrics (dict): metrics 결과
        original_file (str): 원본 파일 경로
        output_dir (str): 출력 디렉토리
        key_count (int): 키 개수 (None이면 자동 감지)
    """
    modes = ['local_nps', 'jack', 'chord', 'hand', 'all']
    
    basename = os.path.basename(original_file)
    name_without_ext = os.path.splitext(basename)[0]
    
    for mode in modes:
        output_file = os.path.join(output_dir, f"{name_without_ext}_DEBUG_{mode}.osu")
        export_debug_osu(notes, metrics, original_file, output_file, mode, key_count)


# ============================================================================
# 테스트 코드
# ============================================================================

if __name__ == '__main__':
    from bms_parser import BMSParser
    from osu_parser import OsuParser
    import metric_calc
    
    # 테스트 파일
    test_file = r'd:\계산기\문제분석용\#Time files [06 XRATE].bml'
    
    print("=" * 60)
    print("디버그 OSU 파일 생성 테스트")
    print("=" * 60)
    print()
    
    # 파싱
    parser = BMSParser(test_file)
    notes = parser.parse()
    
    if notes:
        first_time = notes[0]['time']
        last_time = notes[-1]['time']
        duration = last_time - first_time
        if duration < 1.0:
            duration = 1.0
    else:
        duration = 0
    
    # 메트릭 계산
    metrics = metric_calc.calculate_metrics(notes, duration)
    
    # 출력 디렉토리
    output_dir = r'd:\계산기\debug_osu_output'
    os.makedirs(output_dir, exist_ok=True)
    
    # 여러 모드로 생성 (파서의 키 개수 전달)
    print(f"감지된 키 모드: {parser.detected_mode}, 키 개수: {parser.key_count}")
    export_multiple_modes(notes, metrics, test_file, output_dir, key_count=parser.key_count)
    
    print()
    print("=" * 60)
    print("✅ 모든 디버그 파일 생성 완료!")
    print(f"   출력 위치: {output_dir}")
    print("=" * 60)
