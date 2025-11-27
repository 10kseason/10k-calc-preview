def hp9_score(
    n300: int,
    n200: int,
    n100: int,
    n50: int,
    n_miss: int,
    hp_start: float = 10.0,
) -> float:
    """
    Osu!mania HP9 체감을 기준으로 한
    '정규화 HP 점수' 계산기.

    반환값 hp_end:
      - hp_end > 0  → HP9 기준으로 버팀
      - hp_end <= 0 → HP9 기준으로 사망
    """
    PUNISH_FACTOR_HP9 = 18.75  # 미스 1개 ≒ 300 18.75개
    gain_300 = 1.0 / PUNISH_FACTOR_HP9  # ≈ 0.05333...

    gain_200 = 0.7 * gain_300
    gain_100 = 0.3 * gain_300

    loss_50 = 0.5   # 50 두 개 = 미스 한 개 정도
    loss_miss = 1.0 # 미스 한 개 = HP -1

    hp = hp_start
    hp += gain_300 * n300
    hp += gain_200 * n200
    hp += gain_100 * n100
    hp -= loss_50 * n50
    hp -= loss_miss * n_miss

    return hp

def calculate_max_misses(total_notes: int, hp_start: float = 10.0) -> int:
    """
    Calculate the maximum number of misses allowed to survive HP9,
    assuming all other notes are 300s (Perfects).
    
    Condition: HP > 0
    HP_end = Start + (Total - Miss) * Gain300 - Miss * LossMiss > 0
    Start + Total*Gain - Miss*Gain - Miss*Loss > 0
    Start + Total*Gain > Miss * (Gain + Loss)
    Miss < (Start + Total*Gain) / (Gain + Loss)
    """
    PUNISH_FACTOR_HP9 = 18.75
    gain_300 = 1.0 / PUNISH_FACTOR_HP9
    loss_miss = 1.0
    
    numerator = hp_start + total_notes * gain_300
    denominator = gain_300 + loss_miss
    
    max_miss = numerator / denominator
    return int(max_miss) # Floor value, as exceeding it means death (or <= 0)

def hp9_from_qwilight(
    n_pg: int,    # 피그렛 (PGREAT)
    n_pf: int,    # 퍼펙 (PERFECT)
    n_gr: int,    # GREAT
    n_gd: int,    # GOOD
    n_bd: int,    # BAD
    n_poor: int,  # POOR / MISS
    hp_start: float = 10.0,
) -> float:
    """
    Qwilight 판정 결과를
    'osu!mania HP9 기준 체력'으로 환산하는 함수.

    반환값 hp_end:
      - hp_end > 0  → HP9 기준으로는 클리어
      - hp_end <= 0 → HP9 기준으로는 사망
    """

    PUNISH_FACTOR_HP9 = 18.75  # 미스 1개 ≒ 300 18.75개
    g = 1.0 / PUNISH_FACTOR_HP9  # 300 한 개당 HP 회복량

    # Qwilight → mania 계층 매핑
    n300 = n_pg + n_pf
    n200 = n_gr
    n100 = n_gd
    n50  = n_bd
    n_miss = n_poor

    # 가중치 (필요하면 여기만 손보면 됨)
    gain_300 = g
    gain_200 = 0.7 * g
    gain_100 = 0.3 * g
    loss_50  = 0.5
    loss_miss = 1.0

    hp = hp_start
    hp += gain_300 * n300
    hp += gain_200 * n200
    hp += gain_100 * n100
    hp -= loss_50  * n50
    hp -= loss_miss * n_miss

    return hp
