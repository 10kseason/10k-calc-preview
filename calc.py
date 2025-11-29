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
    cap_start=60.0,
    cap_range=30.0,
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

    var_b = float(np.var(b_t))

    # 축별 기여
    vF = w_F * F_rank_used
    vP = w_P * P_rank_used
    vV = w_V * var_b

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
def pattern_level_from_D0(
    D0: float,
    D_min: float = 0.0,  # Adjusted for D0=0 -> Lv 1
    D_max: float = 75.0, # Adjusted for D0=38 -> Lv 13 (approx D0/3 + 1)
    gamma: float = 1.0,  # Linear mapping fits well
    uncap: bool = False,
) -> float:
    """
    Raw 난이도 D0를 '패턴 레벨(1~25)'로 바로 매핑.

    D0 <= D_min -> 1렙 근처
    D0 >= D_max -> 25렙 근처
    사이 구간은 (정규화 후)^gamma 로 곡선 보정.
    """
    # 1) D0를 [0,1]로 정규화
    x = (D0 - D_min) / (D_max - D_min)
    x = max(0.0, min(1.0, x))  # [0,1] 클램프

    # 2) 곡선 보정
    #   gamma > 1  -> 상단 압축, 하단 확대
    #   gamma < 1  -> 하단 압축, 상단 확대
    x_scaled = x ** gamma

    # 3) 1~25 스케일로 매핑
    base = 1.0 + 24.0 * x_scaled  # 0 -> 1, 1 -> 25

    if not uncap:
        # 정수 레벨로 반올림 + 클램프
        return float(max(1.0, min(25.0, round(base))))
    else:
        # 자유 레벨 (소수 허용, 상한 없음)
        return float(max(1.0, base))

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
    if level < 20: return "초고수"
    return "신"


# ----------------------------
# 6. 전체 파이프라인 예시 함수
# ----------------------------
def compute_map_difficulty(
    nps, ln_strain, jack_pen, roll_pen, alt_cost, hand_strain,
    # 부하 가중치 (Tuned for 10K/14K support)
    # alpha: NPS Weight (0.8) - Reduced to prevent double counting with Hand Strain
    # theta: Hand Strain Weight (0.5) - Reduced for chord-heavy charts
    # eta: Alt Cost Weight (0.5) - Reduced for chord-heavy charts
    alpha=0.8, beta=1.0, gamma=1.0, delta=1.0, eta=0.5, theta=0.5,
    # EMA 람다
    lam_L=0.3, lam_S=0.8,
    # 난이도 가중치 (클리어용)
    w_F=1.0, w_P=1.0, w_V=0.2,
    # Soft Cap
    cap_start=60.0, cap_range=30.0,
    # 로지스틱 파라미터 (로그 피팅 결과)
    # Calibrated for L5 Norm + F-mean scale (D0 approx 4~20)
    # D0=4 -> S=0.67, D0=10 -> S=0.35, D0=17 -> S=0.10
    a=1.64, k=0.250,
    # 전체 DB에서 얻은 F/P 퍼센타일 (없으면 None)
    F_rank=None, P_rank=None,
    # Duration for Level Est
    duration=1.0,
    s_offset=3.0, # Offset for S Rank difficulty (Deprecated but kept for compat)
    total_notes=1000, # Added for Binomial Model
    gamma_clear=1.0, # Added for Gamma Clear Layer
    # S랭 난이도용 별도 가중치 (None이면 자동으로 클리어용에서 파생)
    w_F_s=None, w_P_s=None, w_V_s=None,
    uncap_level=False, # Added for Uncap Level Mode
):
    """
    1) b_t 계산
    2) F, P 계산
    3) D0 계산 (클리어용 / S랭용 분리)
    4) 예측 생존률 S_hat 반환
    5) 예측 레벨 반환
    """
    # 1. 윈도우 부하
    b_t = compute_window_load(
        nps, ln_strain, jack_pen, roll_pen, alt_cost, hand_strain,
        alpha=alpha, beta=beta, gamma=gamma, delta=delta, eta=eta, theta=theta,
        cap_start=cap_start, cap_range=cap_range,
    )

    # 2. 엔듀런스 / 버스트
    F, P, ema_L, ema_S = compute_endurance_and_burst(
        b_t, lam_L=lam_L, lam_S=lam_S
    )

    # 3. 원시 난이도 (클리어용 / S랭용 분리)

    # 3-1) 클리어용 난이도 (기존 D0 그대로)
    D_clear = compute_raw_difficulty(
        F, P, b_t,
        F_rank=F_rank, P_rank=P_rank,
        w_F=w_F, w_P=w_P, w_V=w_V,
        p_norm=5.0,
    )

    # 3-2) S랭용 난이도 (Disabled)
    # D_srank = compute_raw_difficulty(...)
    D_srank = 0.0

    # ★ 3-3. 곡 길이 보정 (Length Bonus)
    # F가 mean으로 바뀌면서 사라진 "곡 길이에 따른 체력 부담"을 보정
    # 1분 미만: 보정 없음 (1.0)
    # 2분: 1.0 + 0.08 * 1 = 1.08 (+8%)
    # 4분: 1.0 + 0.08 * 2 = 1.16 (+16%)
    length_norm = max(duration, 60.0)
    length_bonus = 1.0 + 0.08 * math.log2(length_norm / 60.0)
    
    # Apply bonus to D_clear (Pattern Difficulty)
    D_pattern = D_clear * length_bonus

    # 4. 생존률 예측 (Disabled/Legacy)
    #   - 클리어: 스파이크(F/P/Var)가 크게 박힘
    # S_hat = predict_survival(D_clear, a=a, k=k, gamma_clear=gamma_clear)
    S_hat = 0.0
    
    # S랭 확률 (Disabled)
    # S_rank_prob = predict_s_rank_95(D_srank, a=a, k=k, total_notes=total_notes, acc_target=0.95)
    S_rank_prob = 0.0
    
    # 5. 레벨 예측 (Direct D0 Mapping)
    # est_level = estimate_level(D_clear, uncap=uncap_level)
    pattern_level = pattern_level_from_D0(
        D_pattern,
        D_min=0.0,
        D_max=75.0,
        gamma=1.0,
        uncap=uncap_level
    )
    est_level = int(pattern_level)
    level_label = get_level_label(est_level)

    return {
        "b_t": b_t,
        "F": F,
        "P": P,
        "ema_L": ema_L,
        "ema_S": ema_S,
        "D0": D_pattern, # Return the bonus-applied difficulty
        "S_hat": S_hat,
        "S_rank_prob": S_rank_prob,
        "est_level": est_level,
        "level_label": level_label,
        "pattern_level": pattern_level,
        "length_bonus": length_bonus,
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
