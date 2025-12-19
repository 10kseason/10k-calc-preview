"""
new_calc.py - 선형 회귀 기반 난이도 계산 모델

기존 calc.py의 복잡한 모델 대신, NPS 기반 선형 회귀 모델을 사용합니다.
BMS 데이터 분석 결과, 단순 선형 회귀가 더 정확한 결과를 보여줍니다 (MAE 1.12).
"""

import numpy as np

# ====================================================================
# 모델 파라미터
# ====================================================================

# NPS 선형 회귀 모델 (3-Feature Model)
# level = intercept + coef_nps*global_nps + coef_std*nps_std + coef_chord*chord_mean
# BMS 데이터 1759개 기준 MAE 1.12
NPS_LINEAR_PARAMS = {
    'intercept': -0.1879,
    'coef_nps': 0.2053,
    'coef_std': 0.9999,
    'coef_chord': 3.2741
}

# 레벨 티어 레이블
LEVEL_LABELS = {
    (1, 5): "초보자 (Beginner)",
    (5, 8): "초중수 (Intermediate)",
    (8, 12): "중수 (Skilled)",
    (12, 14): "중고수 (Advanced)",
    (14, 16): "고수 (Expert)",
    (16, 19): "초고수 (Master)",
    (19, 22): "Professional",
    (22, float('inf')): "God"
}


# ====================================================================
# 핵심 함수
# ====================================================================

def predict_level_linear(global_nps, nps_std, chord_mean, params=None):
    """
    선형 회귀 모델로 난이도 레벨 예측
    
    Args:
        global_nps (float): 총 노트수 / 곡 길이
        nps_std (float): NPS 표준편차 (변동성)
        chord_mean (float): 평균 코드 밀도
        params (dict, optional): 모델 파라미터. None이면 기본값 사용
    
    Returns:
        float: 추정 레벨 (1~25+)
    
    Example:
        >>> level = predict_level_linear(51.75, 17.08, 3.32)
        >>> print(f"추정 레벨: {level:.2f}")
    """
    if params is None:
        params = NPS_LINEAR_PARAMS
    
    level = (params['intercept'] + 
             params['coef_nps'] * global_nps + 
             params['coef_std'] * nps_std + 
             params['coef_chord'] * chord_mean)
    
    return round(level, 2)


def predict_level_simple(global_nps, params=None):
    """
    단순 NPS만 사용하는 선형 회귀 모델
    
    Args:
        global_nps (float): 총 노트수 / 곡 길이
        params (dict, optional): 모델 파라미터
    
    Returns:
        float: 추정 레벨
    
    Note:
        이 모델은 NPS만 사용하므로 정확도가 3-feature 모델보다 낮습니다.
        간단한 추정이 필요할 때만 사용하세요.
    """
    # 단순 NPS 선형 회귀: level = 0.6963 * NPS + 1.6395 (MAE 1.55)
    simple_params = {
        'intercept': 1.6395,
        'coef_nps': 0.6963
    }
    
    if params is not None:
        simple_params.update(params)
    
    level = simple_params['intercept'] + simple_params['coef_nps'] * global_nps
    return round(level, 2)


def get_level_label(level):
    """
    레벨 숫자를 티어 레이블로 변환
    
    Args:
        level (float): 레벨 (1~25+)
    
    Returns:
        str: 티어 레이블
    
    Example:
        >>> label = get_level_label(10.5)
        >>> print(label)  # "중수 (Skilled)"
    """
    for (min_lv, max_lv), label in LEVEL_LABELS.items():
        if min_lv <= level < max_lv:
            return label
    return "God"  # 최고 레벨


def calculate_nps_metrics(notes, duration):
    """
    NPS 관련 메트릭 계산 (선형 모델용)
    
    Args:
        notes (list): 노트 리스트
        duration (float): 곡 길이 (초)
    
    Returns:
        dict: {
            'global_nps': 전체 NPS (총 노트수 / 곡 길이),
            'peak_nps': Peak NPS (로컬 NPS 최대값),
            'nps_std': NPS 표준편차 (1초 윈도우 기준),
            'total_notes': 총 노트수
        }
    
    Note:
        - Global NPS: 총 노트수 / 곡 길이
        - Local NPS: 각 노트를 중심으로 ±500ms 구간 내 노트 개수
        - Peak NPS: 모든 로컬 NPS 중 최대값
        - NPS std: 1초 윈도우별 NPS의 표준편차 (변동성 지표)
    """
    total_notes = len(notes)
    global_nps = total_notes / duration if duration > 0 else 0
    
    # Local NPS 계산: 각 노트를 중심으로 ±500ms 구간 내 노트 개수
    local_nps_values = []
    
    for note in notes:
        t = round(note['time'], 3)  # ms 단위로 반올림하여 부동소수점 오차 방지
        
        # ±500ms = ±0.5초 구간
        # 부동소수점 오차 방지: t+0.5 대신 t+0.499999999999 사용 후 <= 비교
        window_start = t - 0.5
        window_end = t + 0.499999999999
        
        # 해당 구간 내의 노트 개수 카운트
        count = sum(1 for n in notes if window_start <= n['time'] <= window_end)
        local_nps_values.append(count)
    
    # Peak NPS: 로컬 NPS 최대값
    peak_nps = max(local_nps_values) if local_nps_values else 0
    
    # NPS 표준편차: 1초 윈도우별 NPS의 변동성 (기존 방식 유지)
    window_nps = []
    for t in range(int(duration) + 1):
        count = sum(1 for n in notes if t <= n['time'] < t + 1)
        window_nps.append(count)
    
    nps_std = np.std(window_nps) if window_nps else 0
    
    return {
        'global_nps': round(global_nps, 2),
        'peak_nps': peak_nps,  # 정수값
        'nps_std': round(nps_std, 2),
        'total_notes': total_notes
    }


def predict_from_notes(notes, duration, chord_mean, use_simple=False, params=None):
    """
    노트 데이터로부터 직접 레벨 예측
    
    Args:
        notes (list): 노트 리스트
        duration (float): 곡 길이 (초)
        chord_mean (float): 평균 코드 밀도 (metric_calc에서 계산)
        use_simple (bool): True면 NPS만 사용하는 단순 모델
        params (dict, optional): 모델 파라미터
    
    Returns:
        dict: {
            'level': 추정 레벨,
            'label': 티어 레이블,
            'global_nps': 전체 NPS,
            'peak_nps': Peak NPS (로컬 NPS 최대값),
            'nps_std': NPS 표준편차,
            'chord_mean': 코드 평균,
            'total_notes': 총 노트수,
            'model': 사용한 모델명
        }
    
    Example:
        >>> result = predict_from_notes(notes, duration, chord_mean)
        >>> print(f"레벨: {result['level']} ({result['label']})")
    """
    metrics = calculate_nps_metrics(notes, duration)
    
    if use_simple:
        level = predict_level_simple(metrics['global_nps'], params)
        model_name = "Simple NPS Linear"
    else:
        level = predict_level_linear(
            metrics['global_nps'], 
            metrics['nps_std'], 
            chord_mean,
            params
        )
        model_name = "3-Feature NPS Linear"
    
    return {
        'level': level,
        'label': get_level_label(level),
        'global_nps': metrics['global_nps'],
        'peak_nps': metrics['peak_nps'],
        'nps_std': metrics['nps_std'],
        'chord_mean': chord_mean,
        'total_notes': metrics['total_notes'],
        'model': model_name
    }


# ====================================================================
# 유틸리티 함수
# ====================================================================

def compare_models(global_nps, nps_std, chord_mean):
    """
    단순 모델과 3-feature 모델 비교
    
    Args:
        global_nps (float): 전체 NPS
        nps_std (float): NPS 표준편차
        chord_mean (float): 코드 평균
    
    Returns:
        dict: 두 모델의 예측 결과
    """
    simple = predict_level_simple(global_nps)
    full = predict_level_linear(global_nps, nps_std, chord_mean)
    
    return {
        'simple_model': {
            'level': simple,
            'label': get_level_label(simple)
        },
        '3feature_model': {
            'level': full,
            'label': get_level_label(full)
        },
        'difference': round(abs(full - simple), 2)
    }


# ====================================================================
# 테스트 코드
# ====================================================================

if __name__ == '__main__':
    print("=" * 60)
    print("new_calc.py - 선형 회귀 NPS 모델 테스트")
    print("=" * 60)
    print()
    
    # 테스트 데이터 (CircusGalop 10K HELL CIRCUS)
    test_data = {
        'global_nps': 51.75,
        'nps_std': 17.08,
        'chord_mean': 3.32
    }
    
    print("테스트 데이터:")
    print(f"  Global NPS: {test_data['global_nps']}")
    print(f"  NPS 표준편차: {test_data['nps_std']}")
    print(f"  Chord 평균: {test_data['chord_mean']}")
    print()
    
    # 3-Feature 모델
    level = predict_level_linear(**test_data)
    label = get_level_label(level)
    print(f"3-Feature 모델 예측:")
    print(f"  레벨: {level}")
    print(f"  티어: {label}")
    print()
    
    # 단순 모델
    simple_level = predict_level_simple(test_data['global_nps'])
    simple_label = get_level_label(simple_level)
    print(f"단순 NPS 모델 예측:")
    print(f"  레벨: {simple_level}")
    print(f"  티어: {simple_label}")
    print()
    
    # 비교
    comparison = compare_models(**test_data)
    print("모델 비교:")
    print(f"  차이: {comparison['difference']} 레벨")
    print()
    
    print("=" * 60)
    print("✅ 테스트 완료!")
    print("=" * 60)
