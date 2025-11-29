import calc
import numpy as np

def test_pattern_level():
    print("Testing Pattern Level Calculation...")
    
    # Test cases: D0 -> Expected Level
    # Formula: Level = 1.1 * D0 + 1.5
    # D0=4 -> 5.9 (6)
    # D0=10 -> 12.5 (12 or 13)
    # D0=17 -> 20.2 (20)
    
    test_d0s = [3.0, 4.0, 10.0, 17.0, 20.0, 25.0]
    
    for d0 in test_d0s:
        level = calc.pattern_level_from_D0(d0, uncap=False)
        print(f"D0: {d0:.2f} -> Level: {level}")
        
    print("\nTesting compute_map_difficulty integration...")
    # Mock metrics
    nps = np.array([10.0] * 10)
    ln_strain = np.zeros(10)
    jack_pen = np.zeros(10)
    roll_pen = np.zeros(10)
    alt_cost = np.zeros(10)
    hand_strain = np.zeros(10)
    
    res = calc.compute_map_difficulty(
        nps, ln_strain, jack_pen, roll_pen, alt_cost, hand_strain,
        duration=10.0, total_notes=100
    )
    
    print("Result Keys:", res.keys())
    print(f"D0: {res['D0']:.2f}")
    print(f"Est Level: {res['est_level']}")
    print(f"S_hat: {res['S_hat']}")
    
    if res['S_hat'] == 0.0 and res['est_level'] > 0:
        print("SUCCESS: S_hat is 0.0 and Level is calculated.")
    else:
        print("FAILURE: Unexpected values.")

    print("\nTesting Length Bonus...")
    # Compare 60s vs 120s
    res_60 = calc.compute_map_difficulty(
        nps, ln_strain, jack_pen, roll_pen, alt_cost, hand_strain,
        duration=60.0, total_notes=600
    )
    res_120 = calc.compute_map_difficulty(
        nps, ln_strain, jack_pen, roll_pen, alt_cost, hand_strain,
        duration=120.0, total_notes=1200
    )
    
    print(f"D0 (60s): {res_60['D0']:.2f}")
    print(f"D0 (120s): {res_120['D0']:.2f}")
    
    ratio = res_120['D0'] / res_60['D0']
    print(f"Ratio (120s/60s): {ratio:.4f}")
    
    expected_ratio = 1.08 # 1.0 + 0.08 * log2(2)
    if abs(ratio - expected_ratio) < 0.01:
        print(f"SUCCESS: Length Bonus applied correctly (Expected ~{expected_ratio}, Got {ratio:.4f})")
    else:
        print(f"FAILURE: Length Bonus mismatch (Expected ~{expected_ratio}, Got {ratio:.4f})")

if __name__ == "__main__":
    test_pattern_level()
