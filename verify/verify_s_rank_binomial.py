import calc
import numpy as np

def test_s_rank_binomial():
    # Test parameters
    a = 8.0
    k = 0.005
    D0 = 1000.0 # High difficulty
    
    # Case 1: Short chart (N=500)
    prob_short = calc.predict_s_rank_95(D0, a, k, total_notes=500, acc_target=0.95)
    
    # Case 2: Long chart (N=2500)
    prob_long = calc.predict_s_rank_95(D0, a, k, total_notes=2500, acc_target=0.95)
    
    print(f"D0={D0}, a={a}, k={k}")
    print(f"Short (N=500): {prob_short:.4f}")
    print(f"Long (N=2500): {prob_long:.4f}")
    
    # Expectation: Long chart should have lower probability if p < 0.95, 
    # or higher probability if p > 0.95 (closer to 0 or 1).
    # Let's check p first.
    p = calc.sigmoid(a - k * D0)
    print(f"Base probability p = {p:.4f}")
    
    if p < 0.95:
        if prob_long < prob_short:
            print("PASS: Long chart has lower S-rank probability (as expected for p < 0.95)")
        else:
            print("FAIL: Long chart probability is not lower")
    else:
        if prob_long > prob_short:
            print("PASS: Long chart has higher S-rank probability (as expected for p > 0.95)")
        else:
            print("FAIL: Long chart probability is not higher")

if __name__ == "__main__":
    test_s_rank_binomial()
