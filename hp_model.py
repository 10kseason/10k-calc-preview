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

def osu_hp_drain_model(
    n300: int, n200: int, n100: int, n50: int, n_miss: int,
    hp_drain_rate: float,
    total_notes: int,
    hp_max: float = 100.0
) -> float:
    """
    Osu!mania HP Drain Model (Approximation)
    Based on HP Drain Rate (0-10).
    """
    # Qwilight → mania mapping
    # n300 is sum of PG+PF
    
    # Ratio = 4.0 + 2.1 * HP
    ratio = 4.0 + 2.1 * hp_drain_rate
    
    loss_miss = 1.0
    gain_300 = 1.0 / ratio
    
    gain_200 = 0.7 * gain_300
    gain_100 = 0.3 * gain_300
    loss_50 = 0.5 * loss_miss
    
    hp = hp_max # Start full
    
    hp += gain_300 * n300
    hp += gain_200 * n200
    hp += gain_100 * n100
    hp -= loss_50 * n50
    hp -= loss_miss * n_miss
    
    # Clamp
    hp = min(hp, hp_max)
    
    return hp

def bms_total_gauge_model(
    n_pg: int, n_pf: int, n_gr: int, n_gd: int, n_bd: int, n_poor: int,
    total_value: float,
    total_notes: int
) -> float:
    """
    BMS Total Gauge Model.
    Clear if >= 80.0
    """
    gain_pg = total_value / max(1, total_notes)
    gain_gr = 0.5 * gain_pg
    gain_gd = 0.2 * gain_pg 
    
    score = 20.0 # Start at 20%
    score += (n_pg + n_pf) * gain_pg
    score += n_gr * gain_gr
    score += n_gd * gain_gd
    score -= n_bd * 2.0
    score -= n_poor * 6.0
    
    # Clamp max at 100? Total Gauge usually caps at 100.
    score = min(100.0, score)
    
    return score

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
    # Dynamic Parameters
    mode: str = 'hp9', # 'hp9', 'osu', 'bms_total'
    hp_drain: float = 8.0, # For Osu
    total_val: float = 160.0, # For BMS
    total_notes: int = 1000,
) -> float:
    """
    Qwilight 판정 결과를
    'osu!mania HP9 기준 체력'으로 환산하는 함수.

    반환값 hp_end:
      - hp_end > 0  → HP9 기준으로는 클리어
      - hp_end <= 0 → HP9 기준으로는 사망
    """

    if mode == 'osu':
        # Osu Mode (Nomod)
        # Returns HP (0-100 scale usually, or 0-10)
        # Let's normalize to "Positive = Clear"
        # Osu pass is HP > 0 at end.
        final_hp = osu_hp_drain_model(
            n300=n300, n200=n200, n100=n100, n50=n50, n_miss=n_miss,
            hp_drain_rate=hp_drain,
            total_notes=total_notes,
            hp_max=10.0 # Use 10.0 scale to match HP9 visual
        )
        return final_hp
        
    elif mode == 'bms_total':
        # BMS Total Gauge
        # Clear if >= 80.0
        # Let's shift so that > 0 is clear.
        # Return (Score - 80.0)
        final_gauge = bms_total_gauge_model(
            n_pg=n_pg, n_pf=n_pf, n_gr=n_gr, n_gd=n_gd, n_bd=n_bd, n_poor=n_poor,
            total_value=total_val,
            total_notes=total_notes
        )
        # If gauge >= 80, it's a clear.
        # So we return (Gauge - 80).
        # If result > 0 -> Clear.
        return final_gauge - 80.0
        
    else:
        # Default HP9
        # Qwilight → mania 계층 매핑
        n300 = n_pg + n_pf
        n200 = n_gr
        n100 = n_gd
        n50  = n_bd
        n_miss = n_poor

        return hp9_score(
            n300=n300,
            n200=n200,
            n100=n100,
            n50=n50,
            n_miss=n_miss,
            hp_start=hp_start,
        )
