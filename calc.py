import numpy as np
import math
import hp_model # Need this for total_difficulty_10k

# ----------------------------
# 1. 윈도우별 부하 b_t 계산
# ----------------------------
def compute_window_load(
    nps,         # np.ndarray, 각 윈도우별 NPS
    ln_strain,   # np.ndarray, 각 윈도우별 LN strain
    jack_pen,    # np.ndarray, 각 윈도우별 잭 패널티
    roll_pen,    # np.ndarray, 각 윈도우별 롤 패널티
    alt_cost,    # np.ndarray, 각 윈도우별 손배치/교차 코스트
    hand_strain, # np.ndarray, 손당 NPS (Max of L/R)
    alpha=1.0,
    beta=1.0,
    gamma=1.0,
    delta=1.0,
    eta=1.0,
    theta=1.0, # Hand Strain Weight
):
    """
    b_t = α*NPS_t + β*LNStrain_t + γ*JackPenalty_t + δ*RollPenalty_t + η*AltCost_t + θ*HandStrain_t
    
    NPS Scaling:
    If NPS > 40: NPS' = 40 + (NPS - 40)^1.2
    """
    nps = np.asarray(nps, dtype=float)
    ln_strain = np.asarray(ln_strain, dtype=float)
    jack_pen = np.asarray(jack_pen, dtype=float)
    roll_pen = np.asarray(roll_pen, dtype=float)
    alt_cost = np.asarray(alt_cost, dtype=float)
    hand_strain = np.asarray(hand_strain, dtype=float)

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
        theta * hand_strain
    )
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

    F = float(np.sum(ema_L))
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
):
    """
    D0 = w_F * Rank(F) + w_P * Rank(P) + w_V * Var(b_t)
    Rank()는 외부에서 퍼센타일로 넣어주는 것을 가정.
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

    var_b = float(np.var(b_t))

    D0 = w_F * F_rank_used + w_P * P_rank_used + w_V * var_b
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


def predict_survival(D0, a, k):
    """
    예측 생존률:
    S_hat = σ(a - k * D0)
    """
    return float(sigmoid(a - k * D0))


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
def estimate_level(P, F, duration):
    """
    Estimate level (1-20) based on Burst Peak (P) and Average Load (F/duration).
    
    Heuristic Formula:
    Level = C1 * P + C2 * (F / duration)
    
    Assuming:
    - P (Peak Load) is dominant factor for difficulty spike.
    - F/duration (Average Load) represents stamina requirement.
    
    Tuning (Example):
    - Level 1: P ~ 2, Avg ~ 1
    - Level 10: P ~ 15, Avg ~ 8
    - Level 20: P ~ 30, Avg ~ 15
    
    Let's try linear fit:
    L = 0.5 * P + 0.5 * Avg
    """
    if duration <= 0: return 1
    
    avg_load = F / duration
    
    # Tuning for 10K High Tier:
    # Target: Peak 60 / Avg 25 -> Level 20
    # Target: Peak 25 / Avg 10 -> Level 10 (approx)
    
    # Let's try:
    # 0.25 * 60 + 0.2 * 25 = 15 + 5 = 20. Perfect.
    # 0.25 * 25 + 0.2 * 10 = 6.25 + 2 = 8.25. A bit low?
    # Maybe add a base constant? Or adjust weights.
    # Let's try: Level = 0.28 * P + 0.15 * Avg
    # 0.28 * 60 + 0.15 * 25 = 16.8 + 3.75 = 20.55 (Clamped to 19/20)
    # 0.28 * 25 + 0.15 * 10 = 7.0 + 1.5 = 8.5.
    
    # Let's stick to the user suggestion or simple fit.
    # User said: "Just re-calibrate mapping".
    # Let's use: Level = 0.25 * P + 0.2 * Avg for now.
    
    est = 0.25 * P + 0.2 * avg_load
    
    # Clamp to 1-20
    est = max(1.0, min(20.0, est))
    
    return int(round(est))

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
    
    Handling overlaps by favoring the higher tier for the boundary start?
    Let's assume:
    1 <= L < 5: 초보자
    5 <= L < 9: 초중수
    9 <= L < 12: 중수
    12 <= L < 14: 중고수
    14 <= L < 16: 고수
    16 <= L <= 19: 초고수
    """
    if level < 5: return "초보자"
    if level < 9: return "초중수"
    if level < 12: return "중수"
    if level < 14: return "중고수"
    if level < 16: return "고수"
    return "초고수"


# ----------------------------
# 6. 전체 파이프라인 예시 함수
# ----------------------------
def compute_map_difficulty(
    nps, ln_strain, jack_pen, roll_pen, alt_cost, hand_strain,
    # 부하 가중치
    alpha=1.0, beta=1.0, gamma=1.0, delta=1.0, eta=1.0, theta=1.0,
    # EMA 람다
    lam_L=0.3, lam_S=0.8,
    # 난이도 가중치
    w_F=1.0, w_P=1.0, w_V=0.2,
    # 로지스틱 파라미터 (로그 피팅 결과)
    a=0.0, k=1.0,
    # 전체 DB에서 얻은 F/P 퍼센타일 (없으면 None)
    F_rank=None, P_rank=None,
    # Duration for Level Est
    duration=1.0,
):
    """
    1) b_t 계산
    2) F, P 계산
    3) D0 계산
    4) 예측 생존률 S_hat 반환
    5) 예측 레벨 반환
    """
    # 1. 윈도우 부하
    b_t = compute_window_load(
        nps, ln_strain, jack_pen, roll_pen, alt_cost, hand_strain,
        alpha=alpha, beta=beta, gamma=gamma, delta=delta, eta=eta, theta=theta,
    )

    # 2. 엔듀런스 / 버스트
    F, P, ema_L, ema_S = compute_endurance_and_burst(
        b_t, lam_L=lam_L, lam_S=lam_S
    )

    # 3. 원시 난이도
    D0 = compute_raw_difficulty(
        F, P, b_t,
        F_rank=F_rank, P_rank=P_rank,
        w_F=w_F, w_P=w_P, w_V=w_V,
    )

    # 4. 생존률 예측
    S_hat = predict_survival(D0, a=a, k=k)
    
    # 5. 레벨 예측
    est_level = estimate_level(P, F, duration)
    level_label = get_level_label(est_level)

    return {
        "b_t": b_t,
        "F": F,
        "P": P,
        "ema_L": ema_L,
        "ema_S": ema_S,
        "D0": D0,
        "S_hat": S_hat,
        "est_level": est_level,
        "level_label": level_label,
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
    10-Key용 패턴 난이도 축.
    리턴값은 대략 1 ~ 30 사이 정도로 나오게 튜닝됨.
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
    hp_end: hp9_from_qwilight() 결과.
    반환값: 1.0 ~ 3.0 사이의 난이도 배율.
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
    10-Key 총 난이도 계산기.
    - pattern_diff : 맵 자체 패턴 난이도 (1 ~ 30 대략)
    - hp_factor    : HP9 기준 체력 난이도 배율 (1.0 ~ 3.0)
    - total_diff   : 둘을 곱한 총 난이도 값
    - level        : 표시용 레벨 (sqrt(total_diff))
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
