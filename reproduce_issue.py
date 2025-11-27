import numpy as np
import calc

def test_calibration():
    # Simulate a 120s chart with Avg Density 14, Peak 35
    duration = 120
    n_windows = duration  # 1s windows
    
    # Create a base load of 14
    b_t = np.full(n_windows, 14.0)
    
    # Add a peak of 35 in the middle
    # To maintain average of 14, we need to lower other parts or just accept slight deviation
    # Let's just set one window to 35 and adjust others to keep mean ~ 14
    # Sum = 14 * 120 = 1680
    # Current Sum = 1680
    # Set b_t[60] = 35 (increase by 21)
    # Decrease others by 21 / 119 ~ 0.17
    
    b_t[60] = 35.0
    correction = (35.0 - 14.0) / (n_windows - 1)
    for i in range(n_windows):
        if i != 60:
            b_t[i] -= correction
            
    print(f"Mean Load: {np.mean(b_t):.2f}")
    print(f"Max Load: {np.max(b_t):.2f}")
    
    # Calculate F, P
    # Using default lambdas
    F, P, ema_L, ema_S = calc.compute_endurance_and_burst(b_t)
    
    print(f"F (Endurance): {F:.2f}")
    print(f"P (Burst): {P:.2f}")
    
    # Calculate D0 with default weights
    D0 = calc.compute_raw_difficulty(F, P, b_t)
    print(f"D0 (Raw Diff): {D0:.2f}")
    
    # Calculate S_hat with new defaults (a=7.97, k=0.005)
    # We don't need to pass a/k if defaults are updated, but let's pass them explicitly to be sure or check defaults
    # Actually, let's check if calc.compute_map_difficulty uses them by default
    
    # Using defaults from calc.py
    # Note: predict_survival doesn't have defaults in signature, we need to pass them or use compute_map_difficulty
    # But let's test the values we put in calc.py
    
    a_new = 7.97
    k_new = 0.005
    
    S_hat = calc.predict_survival(D0, a=a_new, k=k_new)
    print(f"S_hat (New Defaults): {S_hat:.4f}")
    
    target_prob = 0.3575
    diff = S_hat - target_prob
    print(f"Difference from target: {diff:.4f}")
    
    if abs(diff) < 0.01:
        print("SUCCESS: Calibration verified.")
    else:
        print("FAILURE: Calibration off.")
        
    # Verify Level Estimation
    # S_hat = 0.3572 -> Level should be around 11
    est_level = calc.estimate_level(S_hat)
    print(f"Estimated Level: {est_level}")
    
    if est_level in [10, 11, 12]:
        print("SUCCESS: Level estimation is reasonable (Middle Tier).")
    else:
        print("FAILURE: Level estimation is off.")

if __name__ == "__main__":
    test_calibration()
