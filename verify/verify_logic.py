import bms_parser
import metric_calc
import calc
import numpy as np

def verify():
    print("Verifying BMS Difficulty Calculator Pipeline...")
    
    # 1. Test Parser
    print("\n[1] Testing Parser...")
    parser = bms_parser.BMSParser("d:/계산기/test_sample.bms")
    notes = parser.parse()
    print(f"Parsed {len(notes)} notes.")
    print(f"Duration: {parser.duration:.2f}s")
    
    if len(notes) == 0:
        print("FAIL: No notes parsed.")
        return
    
    # Check BPM change effect (Measure 4 has 150 BPM -> 96 hex)
    # Measure 1-3: 120 BPM. 4 beats per measure. 2 seconds per measure.
    # Measure 4: 150 BPM. 4 beats. 60/150 * 4 = 1.6 seconds.
    # Total duration should be around 2*3 + 1.6 = 7.6s.
    print(f"Expected Duration approx 7.6s. Actual: {parser.duration:.2f}s")
    
    # 2. Test Metric Calc
    print("\n[2] Testing Metric Calculation...")
    metrics = metric_calc.calculate_metrics(notes, parser.duration)
    print("Metrics calculated:")
    for k, v in metrics.items():
        print(f"  {k}: shape {v.shape}, max {np.max(v):.2f}, mean {np.mean(v):.2f}")
        
    if np.max(metrics['nps']) == 0:
        print("FAIL: Max NPS is 0.")
        return
        
    # 3. Test Difficulty Calc
    print("\n[3] Testing Difficulty Calculation...")
    result = calc.compute_map_difficulty(
        metrics['nps'], metrics['ln_strain'], metrics['jack_pen'], 
        metrics['roll_pen'], metrics['alt_cost'], metrics['hand_strain']
    )
    
    print("Difficulty Results:")
    print(f"  F (Endurance): {result['F']:.2f}")
    print(f"  P (Burst Peak): {result['P']:.2f}")
    print(f"  D0 (Raw Difficulty): {result['D0']:.2f}")
    print(f"  S_hat (Survival): {result['S_hat']:.2%}")
    
    print("\nVerification Complete. Pipeline seems functional.")

if __name__ == "__main__":
    verify()
