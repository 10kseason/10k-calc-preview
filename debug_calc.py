import os
import bms_parser
import metric_calc
import calc
import numpy as np

def debug_file(file_path):
    print(f"Debugging file: {file_path}")
    
    # 1. Parse
    parser = bms_parser.BMSParser(file_path)
    notes = parser.parse()
    if not notes:
        print("No notes found.")
        return

    duration = notes[-1]['time'] - notes[0]['time'] if notes else 0
    print(f"Duration: {duration:.2f}s, Notes: {len(notes)}")

    # 2. Metrics
    metrics = metric_calc.calculate_metrics(notes, duration)
    
    nps = metrics['nps']
    ln_strain = metrics['ln_strain']
    jack_pen = metrics['jack_pen']
    roll_pen = metrics['roll_pen']
    alt_cost = metrics['alt_cost']
    hand_strain = metrics['hand_strain']
    chord_strain = metrics['chord_strain']

    # 3. Component Analysis
    print("\n=== Component Max Values ===")
    print(f"NPS Max: {np.max(nps):.2f}")
    print(f"LN Strain Max: {np.max(ln_strain):.2f}")
    print(f"Jack Penalty Max: {np.max(jack_pen):.2f}")
    print(f"Roll Penalty Max: {np.max(roll_pen):.2f}")
    print(f"Alt Cost Max: {np.max(alt_cost):.2f}")
    print(f"Hand Strain Max: {np.max(hand_strain):.2f}")
    print(f"Chord Strain Max: {np.max(chord_strain):.2f}")

    # 4. Reconstruct b_t (Raw)
    # Using default weights from calc.py
    alpha=0.8
    beta=1.0
    gamma=1.0
    delta=1.0
    eta=0.5
    theta=0.5
    omega=1.5
    
    # Non-linear NPS Scaling (same as calc.py)
    nps_scaled = np.copy(nps)
    mask = nps_scaled > 40.0
    nps_scaled[mask] = 40.0 + (nps_scaled[mask] - 40.0) ** 1.2

    b_raw = (
        alpha * nps_scaled +
        beta * ln_strain +
        gamma * jack_pen +
        delta * roll_pen +
        eta * alt_cost + 
        theta * hand_strain +
        omega * chord_strain
    )
    
    print(f"\nRaw b_t Max: {np.max(b_raw):.2f}")
    
    # 5. Soft Cap
    b_capped = calc.soft_cap_load(b_raw, cap_start=60.0, cap_range=30.0)
    print(f"Capped b_t Max: {np.max(b_capped):.2f}")
    
    # 6. D0 Calculation (Std)
    F, P, _, _ = calc.compute_endurance_and_burst(b_capped)
    std_b = np.std(b_capped)
    
    print(f"\nF: {F:.2f}")
    print(f"P: {P:.2f}")
    print(f"Std(b_t): {std_b:.2f}")
    
    D0 = calc.compute_raw_difficulty(F, P, b_capped, w_V=0.2, p_norm=5.0)
    print(f"D0: {D0:.2f}")

if __name__ == "__main__":
    target_file = r"d:\계산기\테스트 샘플\10K2S\10K2S ARCADE\We are the xxxx\#We are the xxxx [01 EASY].bml"
    debug_file(target_file)
