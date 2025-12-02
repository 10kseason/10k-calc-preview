import numpy as np
import math
import hp_model # Need this for total_difficulty_10k

# ----------------------------
# 1. 윈도우별 부하 b_t 계산
# ----------------------------
def soft_cap_load(b_t, cap_start=60.0, cap_range=30.0):
    """
    부드러운 상한을 주는 soft cap.

    cap_start = T  : 이 값까지는 그대로 사용
    cap_range = C  : cap_start 위로 최대 cap_range 만큼만 더 올라감
                     (즉 cap_start + cap_range 근처로 수렴)
    """
    b_t = np.asarray(b_t, dtype=float)
    out = b_t.copy()

    mask = out > cap_start
    x = out[mask] - cap_start  # 초과분

    # b' = T + (b - T) * C / (C + (b - T))
    out[mask] = cap_start + x * (cap_range / (cap_range + x))
    return out


# ----------------------------
# 1. 윈도우별 부하 b_t 계산 (Modified)
# ----------------------------
def compute_window_load(
    nps,         # np.ndarray, 각 윈도우별 NPS
    ln_strain,   # np.ndarray, 각 윈도우별 LN strain
    jack_pen,    # np.ndarray, 각 윈도우별 잭 패널티
    roll_pen,    # np.ndarray, 각 윈도우별 롤 패널티
    alt_cost,    # np.ndarray, 각 윈도우별 손배치/교차 코스트
    hand_strain, # np.ndarray, 손당 NPS (Max of L/R)
    chord_strain,# [NEW] np.ndarray, 동시치기 부하 (Sum of (ChordSize-1))
    alpha=1.0,
    beta=1.0,
    gamma=1.0,
    delta=1.0,
    eta=1.0,
    theta=1.0, 
    omega=1.0,   # [NEW] Chord Weight
    cap_start=60.0,
    cap_range=30.0,
):
    """
    b_t = α*NPS + β*LN + γ*Jack + δ*Roll + η*Alt + θ*Hand + ω*Chord
    """
    nps = np.asarray(nps, dtype=float)
    ln_strain = np.asarray(ln_strain, dtype=float)
    jack_pen = np.asarray(jack_pen, dtype=float)
    roll_pen = np.asarray(roll_pen, dtype=float)
    alt_cost = np.asarray(alt_cost, dtype=float)
    hand_strain = np.asarray(hand_strain, dtype=float)
    chord_strain = np.asarray(chord_strain, dtype=float) # [NEW]

    # Non-linear NPS Scaling for high density
    nps_scaled = np.copy(nps)
    mask = nps_scaled > 40.0
    nps_scaled[mask] = 40.0 + (nps_scaled[mask] - 40.0) ** 1.2

    b_t = (
        alpha * nps_scaled +
        beta * ln_strain +
        gamma * jack_pen +
        delta * roll_pen +
        eta * alt_cost + 
        theta * hand_strain +
        omega * chord_strain # [NEW] 동시치기 가중치 합산
    )
    
    # Soft Cap 적용
    b_t = soft_cap_load(b_t, cap_start=cap_start, cap_range=cap_range)
    
    return b_t


# ----------------------------
# 2. EMA 기반 피로 / 피크 계산
# ----------------------------
def ema(x, lam):
    """
    단순 지수이동평균 (EMA)
    lam: 0~1 사이 추천 (1에 가까울수록 최신값 비중↑)
    """
    x = np.asarray(x, dtype=float)
    out = np.empty_like(x)
    out[0] = x[0]
    for i in range(1, len(x)):
        out[i] = lam * x[i] + (1.0 - lam) * out[i-1]
    return out


def compute_endurance_and_burst(b_t, lam_L=0.3, lam_S=0.8):
    """
    엔듀런스 피로 F, 버스트 피크 P 계산
    F = sum_t EMA_L(b_t)
    P = max_t EMA_S(b_t)
    """
    b_t = np.asarray(b_t, dtype=float)

    ema_L = ema(b_t, lam_L)   # 긴 타임스케일 (엔듀런스)
    ema_S = ema(b_t, lam_S)   # 짧은 타임스케일 (버스트)

    F = float(np.mean(ema_L))
    P = float(np.max(ema_S))
    return F, P, ema_L, ema_S

# ----------------------------
# 3. 원시 난이도 D0 계산
# ----------------------------
def compute_raw_difficulty(
    F, P, b_t,
    F_rank=None,  # 전체 곡 DB 기준 F 퍼센타일 (0~1), 없으면 F 자체를 사용
    P_rank=None,  # 전체 곡 DB 기준 P 퍼센타일 (0~1), 없으면 P 자체를 사용
    w_F=1.0,
    w_P=1.0,
    w_V=0.2,
    p_norm=5.0,
):
    """
    D0 = || ( w_F * Rank(F), w_P * Rank(P), w_V * Var(b_t) ) ||_p

    p_norm = 1.0 이면 기존과 같은 L1 (선형 가중합).
    p_norm > 1.0 이면 큰 축을 더 강조하는 L^p 노름.
    """
    b_t = np.asarray(b_t, dtype=float)

    if F_rank is None:
        F_rank_used = float(F)
    else:
        F_rank_used = float(F_rank)

    if P_rank is None:
        P_rank_used = float(P)
    else:
        P_rank_used = float(P_rank)

    # 🔧 여기 변경
    std_b = float(np.std(b_t))   # <= 분산 대신 표준편차
    vF = w_F * F_rank_used
    vP = w_P * P_rank_used
    vV = w_V * std_b

    if p_norm is None or p_norm == 1.0:
        # 기존 L1 방식
        D0 = vF + vP + vV
    else:
        p = float(p_norm)
        D0 = (abs(vF)**p + abs(vP)**p + abs(vV)**p)**(1.0 / p)

    return D0


# ----------------------------
# 4. 생존률 예측 로지스틱 모델
# ----------------------------
def sigmoid(x):
    # Prevent overflow in exp
    # np.exp(-x) overflows if x is very large negative number (e.g. -800)
    # We can clip x to a safe range, e.g., [-100, 100]
    # Since sigmoid(-100) is effectively 0 and sigmoid(100) is 1.
    x = np.clip(x, -100.0, 100.0)
    return 1.0 / (1.0 + np.exp(-x))


def logit(p):
    """
    σ^{-1}(p) = log(p / (1-p))
    """
    p = np.clip(p, 1e-6, 1.0 - 1e-6)
    return np.log(p / (1.0 - p))


def predict_survival(D0, a, k, gamma_clear=1.0):
    """
    예측 생존률:
    기존: S_hat = σ(a - k * D0)
    수정: S_hat = (σ(a - k * D0)) ** gamma_clear
    """
    base = sigmoid(a - k * D0)
    # 수치 안정성용 살짝 클램프
    base = max(1e-6, min(1.0 - 1e-6, base))
    return float(base ** gamma_clear)


def predict_s_rank(D0, a, k, offset):
    """
    [DEPRECATED] Old Offset Model
    예측 S랭크 확률 (OD 8 기준)
    S_prob = σ(a - k * D0 - offset)
    """
    return float(sigmoid(a - k * D0 - offset))


def normal_cdf(x: float) -> float:
    # 표준 정규분포 CDF Φ(x)
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def predict_s_rank_95(D0: float, a: float, k: float,
                      total_notes: int,
                      acc_target: float = 0.95) -> float:
    """
    10키용 S랭 확률 (정확도 >= acc_target, 기본 95%) 예측

    1) p = σ(a - k * D0)  : 한 노트를 '좋게' 칠 확률
    2) N = total_notes    : 노트 수
    3) Acc ~ N(p, p(1-p)/N) 가정
    4) P(Acc >= acc_target) ≈ Φ( (p - acc_target) / sqrt(p(1-p)/N) )
    """

    # 1. 한 노트 정확도 확률
    p = sigmoid(a - k * D0)
    # 수치 안정성용 클램프
    eps = 1e-6
    p = max(min(p, 1.0 - eps), eps)

    # 2. 평균 정확도 분산
    var_mean = p * (1.0 - p) / max(total_notes, 1)
    sigma_mean = math.sqrt(var_mean)

    # 3. Z-score
    z = (p - acc_target) / sigma_mean

    # 4. 표준정규 CDF로 확률 변환
    return normal_cdf(z)


def target_D0_for_survival(S_target, a, k):
    """
    목표 생존률 S_target일 때의 '임계 난이도' D0* 계산:

    S_target = σ(a - k * D0*)
    => a - k * D0* = logit(S_target)
    => D0* = (a - logit(S_target)) / k
    """
    return float((a - logit(S_target)) / k)

# ----------------------------
# 5. 레벨 예측 (1~20)
# ----------------------------
# ----------------------------
# 5. 레벨 예측 (1~20)
# ----------------------------
def pattern_level_from_D0(
    D0: float,
    D_min: float = 0.0,
    D_max: float = 55.0, # [수정] 90 -> 55 (Jack Pen fix 후 재조정)
    gamma: float = 1.0,
    uncap: bool = False,
) -> float:
    """
    Raw 난이도 D0를 '패턴 레벨'로 매핑.
    
    uncap=False (Default):
      - Range: 1 ~ 25
      - Formula: 1 + 24 * x^gamma
      - Clamped at D_max (x=1)
      
    uncap=True (Debug Mode):
      - Range: 0 ~ 100+
      - Formula: 100 * x^gamma
      - No upper clamp. D_max corresponds to Level 100.
    """
    if uncap:
        # Debug Scale: 0 at D_min, 100 at D_max, extends beyond 100
        x = (D0 - D_min) / (D_max - D_min)
        x = max(0.0, x) # No upper clamp
        x_scaled = x ** gamma
        return float(100.0 * x_scaled)
    else:
        # Standard Scale: 1 at D_min, 25 at D_max, clamped
        x = (D0 - D_min) / (D_max - D_min)
        x = max(0.0, min(1.0, x))
        x_scaled = x ** gamma
        base = 1.0 + 24.0 * x_scaled
        
        # Band-wise Level Correction (Antigravity v0.1)
        # Based on residual analysis:
        # - Low (< 12): -1.5 (Fix overprediction)
        # - Trans (12-13): -1.5 -> 0.0
        # - Trans (13-14): 0.0 -> +1.5
        # - High (14-17): +1.5 (Fix underprediction)
        # - Trans (17-19): +1.5 -> +5.0
        # - Top (> 19): +5.0
        
        level = base
        if level < 12.0:
            level = max(1.0, level - 1.5)
        elif level < 13.0:
            t = level - 12.0
            level = level - 1.5 * (1.0 - t)
        elif level < 14.0:
            t = level - 13.0
            level = level + 1.5 * t
        elif level < 17.0:
            level = level + 1.5
        elif level < 19.0:
            t = (level - 17.0) / 2.0
            level = level + 1.5 + (3.5 * t)
        else:
            level = level + 5.0
            
        return float(max(1.0, min(25.0, level)))

def estimate_level(D0, uncap=False):
    """
    [LEGACY WRAPPER]
    Redirects to pattern_level_from_D0 for backward compatibility if needed,
    but ideally should be replaced.
    """
    return int(pattern_level_from_D0(D0, uncap=uncap))

def get_level_label(level):
    """
    Returns the skill tier label for a given level (1-19).
    Ranges:
    1~5: 초보자
    5~8: 초중수
    9~12: 중수
    12~14: 중고수
    14~16: 고수
    16~19: 초고수
    """
    if level < 5: return "초보자"
    if level < 9: return "초중수"
    if level < 12: return "중수"
    if level < 14: return "중고수"
    if level < 16: return "고수"
    if level < 20: return "초고수"
    return "신"


# ----------------------------
# 6. 전체 파이프라인 함수 (Modified)
# ----------------------------
def compute_map_difficulty(
    nps, ln_strain, jack_pen, roll_pen, alt_cost, hand_strain, 
    chord_strain, # [NEW] Input required
    # 부하 가중치
    alpha=0.8, beta=1.0, gamma=1.0, delta=1.0, eta=0.5, theta=0.5,
    omega=1.5, # [NEW] Chord Weight (기본값 1.5 추천 - 동시치기는 체력 소모가 큼)
    # EMA 람다
    lam_L=0.3, lam_S=0.8,
    # 난이도 가중치
    w_F=1.0, w_P=1.0, w_V=0.2,
    # Soft Cap
    cap_start=60.0, cap_range=30.0,
    # 로지스틱 파라미터
    a=1.64, k=0.250,
    # 기타
    F_rank=None, P_rank=None,
    duration=1.0,
    total_notes=1000,
    gamma_clear=1.0,
    uncap_level=False,
    # Level Mapping Params
    D_min=0.0,   # [NEW] Calibrated D_min
    D_max=55.0,  # [수정] 90 -> 55
    gamma_curve=1.0,
    level_offset=0.0, # [NEW] Fixed Level Offset (e.g. for Osu)
    # Legacy args ignored
    s_offset=None, w_F_s=None, w_P_s=None, w_V_s=None,
):
    """
    Chord Strain을 포함한 난이도 계산 파이프라인
    """
    # 1. 윈도우 부하 (chord_strain, omega 추가됨)
    b_t = compute_window_load(
        nps, ln_strain, jack_pen, roll_pen, alt_cost, hand_strain, chord_strain,
        alpha=alpha, beta=beta, gamma=gamma, delta=delta, eta=eta, theta=theta, omega=omega,
        cap_start=cap_start, cap_range=cap_range,
    )

    # 2. 엔듀런스 / 버스트
    F, P, ema_L, ema_S = compute_endurance_and_burst(
        b_t, lam_L=lam_L, lam_S=lam_S
    )

    # 3. 클리어용 난이도 (D0)
    D_clear = compute_raw_difficulty(
        F, P, b_t,
        F_rank=F_rank, P_rank=P_rank,
        w_F=w_F, w_P=w_P, w_V=w_V,
        p_norm=5.0,
    )

    # 4. 곡 길이 보정 [수정] 약화 (log2 -> log1p) + 밀도 보정 (User Feedback)
    # length_bonus를 total_notes / (duration * avg_nps)로 노멀라이즈.
    # avg_nps를 15.0 (Dense Chart 기준)으로 가정.
    length_norm = max(duration, 60.0)
    base_bonus = 0.05 * np.log1p((length_norm - 60.0) / 60.0)
    
    # Density Factor: (TotalNotes / Duration) / 15.0
    # NPS가 15 이상이면 1.0 (Full Bonus), 낮으면 감쇠
    avg_nps = total_notes / max(1.0, duration)
    density_factor = min(1.0, avg_nps / 15.0)
    
    length_bonus = 1.0 + base_bonus * density_factor
    
    D_pattern = D_clear * length_bonus

    # 5. 레벨 예측
    pattern_level = pattern_level_from_D0(
        D_pattern,
        D_min=D_min,
        D_max=D_max,
        gamma=gamma_curve,
        uncap=uncap_level
    )
    
    # [NEW] Apply Offset
    pattern_level += level_offset
    
    est_level = int(pattern_level)
    level_label = get_level_label(est_level)

    return {
        "b_t": b_t,
        "F": F,
        "P": P,
        "ema_L": ema_L,
        "ema_S": ema_S,
        "D0": D_pattern,
        "est_level": est_level,
        "level_label": level_label,
        "pattern_level": pattern_level,
        "length_bonus": length_bonus,
        "chord_strain": chord_strain # 디버깅용 리턴 추가
    }

# --------------------------------------
# 7. 목표 생존률 별 난이도 기준선 예시
# --------------------------------------
def get_difficulty_baseline_for_targets(a, k, targets=(0.5825, 0.8)):
    """
    여러 목표 생존률에 대해 '임계 D0'를 한 번에 뽑는 헬퍼.
    예: 58.25%, 80% 라더 기준 등.
    """
    baselines = {}
    for S in targets:
        baselines[S] = target_D0_for_survival(S, a=a, k=k)
    return baselines

# --------------------------------------
# 8. 패턴 난이도 및 총 난이도 계산
# --------------------------------------
def pattern_difficulty_10k(
    nps_peak: float,
    ln_ratio: float,
    jack_density: float,
    chord_avg: float,
    length_sec: float,
) -> float:
    """
    [LEGACY] 10-Key용 패턴 난이도 축.
    Use compute_map_difficulty for modern, pure difficulty measurement.
    """

    # 속도/밀도 베이스
    S = nps_peak ** 0.85

    # LN 비율 보정
    B_ln = 1.0 + 0.5 * (ln_ratio ** 1.2)

    # 잭 밀도 보정
    B_jack = 1.0 + 0.7 * (jack_density ** 1.1)

    # 평균 동시치기 보정 (싱글=1, 점프=2, 코드=3…)
    c_plus = max(chord_avg - 1.0, 0.0)
    B_chord = 1.0 + 0.3 * c_plus

    # 곡 길이 보정 (1분 이후부터만 살짝 증가)
    length_norm = max(length_sec, 60.0)
    B_len = 1.0 + 0.08 * math.log2(length_norm / 60.0)

    pattern_diff = S * B_ln * B_jack * B_chord * B_len
    return pattern_diff

def hp_difficulty_factor_from_hp9(hp_end: float, hp_start: float = 10.0) -> float:
    """
    [LEGACY] HP 결과에 따른 난이도 배율 보정.
    Pure difficulty measurement should not depend on HP outcome.
    """
    m = hp_end / hp_start
    m = max(-1.0, min(1.0, m))  # [-1, 1]로 클램프
    hp_factor = 2.0 - m         # m=1 -> 1.0, m=0 -> 2.0, m=-1 -> 3.0
    return hp_factor

def total_difficulty_10k(
    # 패턴 스탯
    nps_peak: float,
    ln_ratio: float,
    jack_density: float,
    chord_avg: float,
    length_sec: float,
    # Qwilight 리절트
    n_pg: int,
    n_pf: int,
    n_gr: int,
    n_gd: int,
    n_bd: int,
    n_poor: int,
    hp_start: float = 10.0,
):
    """
    [LEGACY] 10-Key 총 난이도 계산기 (HP 보정 포함).
    This function mixes pattern difficulty with HP survival results, which is now considered legacy.
    Please rely on compute_map_difficulty['est_level'] for pure difficulty.
    """

    # 1) 패턴 난이도
    pattern_diff = pattern_difficulty_10k(
        nps_peak=nps_peak,
        ln_ratio=ln_ratio,
        jack_density=jack_density,
        chord_avg=chord_avg,
        length_sec=length_sec,
    )

    # 2) Qwilight → HP9 → HP 난이도 배율
    hp_end = hp_model.hp9_from_qwilight(
        n_pg=n_pg,
        n_pf=n_pf,
        n_gr=n_gr,
        n_gd=n_gd,
        n_bd=n_bd,
        n_poor=n_poor,
        hp_start=hp_start,
    )
    hp_factor = hp_difficulty_factor_from_hp9(hp_end, hp_start=hp_start)

    # 3) 총 난이도 & 표기 레벨
    total_diff = pattern_diff * hp_factor
    level = math.sqrt(total_diff)

    return {
        "pattern_diff": pattern_diff,
        "hp_end": hp_end,
        "hp_factor": hp_factor,
        "total_diff": total_diff,
        "level": level,
    }
