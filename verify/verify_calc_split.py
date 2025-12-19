import numpy as np
import calc

def verify_calc_split():
    # Dummy data
    nps = np.random.rand(100) * 10
    ln_strain = np.random.rand(100)
    jack_pen = np.random.rand(100)
    roll_pen = np.random.rand(100)
    alt_cost = np.random.rand(100)
    hand_strain = np.random.rand(100)

    # Call compute_map_difficulty
    result = calc.compute_map_difficulty(
        nps, ln_strain, jack_pen, roll_pen, alt_cost, hand_strain,
        w_F=1.0, w_P=1.0, w_V=0.2,
        w_F_s=1.0, w_P_s=0.5, w_V_s=0.1 # Explicit S-rank weights for testing
    )

    # Check keys
    if "D0" not in result:
        print("FAIL: D0 (Clear Difficulty) missing from result.")
        return
    if "D0_srank" not in result:
        print("FAIL: D0_srank (S-Rank Difficulty) missing from result.")
        return

    D_clear = result["D0"]
    D_srank = result["D0_srank"]

    print(f"D_clear: {D_clear}")
    print(f"D_srank: {D_srank}")

    if D_clear == D_srank:
        print("WARNING: D_clear and D_srank are identical. This might be intended if weights are same, but check logic.")
    else:
        print("SUCCESS: D_clear and D_srank are distinct.")

    # Test default S-rank weights
    result_default = calc.compute_map_difficulty(
        nps, ln_strain, jack_pen, roll_pen, alt_cost, hand_strain,
        w_F=1.0, w_P=1.0, w_V=0.2
        # No explicit S-rank weights
    )
    
    D_clear_def = result_default["D0"]
    D_srank_def = result_default["D0_srank"]
    
    print(f"Default D_clear: {D_clear_def}")
    print(f"Default D_srank: {D_srank_def}")
    
    if D_clear_def != D_srank_def:
         print("SUCCESS: Default S-rank weights produced distinct difficulty.")
    else:
         print("WARNING: Default S-rank weights produced identical difficulty.")

if __name__ == "__main__":
    verify_calc_split()
