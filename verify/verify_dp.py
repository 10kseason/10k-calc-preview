import bms_parser
import metric_calc
import calc
import numpy as np

def verify_dp():
    print("Verifying DP Support...")
    
    # 1. Test Parser
    print("\n[1] Testing Parser with DP file...")
    parser = bms_parser.BMSParser("d:/계산기/test_dp.bms")
    notes = parser.parse()
    print(f"Parsed {len(notes)} notes.")
    
    # Check if we have notes > col 7
    max_col = 0
    for n in notes:
        max_col = max(max_col, n['column'])
        
    print(f"Max Column: {max_col}")
    if max_col > 7:
        print("PASS: Detected DP columns (8-15).")
    else:
        print("FAIL: Did not detect DP columns.")
        
    # 2. Test Metric Calc (Alt Cost)
    print("\n[2] Testing Metric Calculation (Alt Cost)...")
    metrics = metric_calc.calculate_metrics(notes, parser.duration)
    
    # In Measure 1:
    # 1P (Left) has 4 notes (Col 1)
    # 2P (Right) has 4 notes (Col 9 -> mapped from 22)
    # Alt Cost should be |4 - 4| = 0?
    # Wait, Col 1 is Left Hand. Col 9 is Right Hand.
    # Logic: 1P Side (0-7) vs 2P Side (8-15).
    # Measure 1: 1P has 4 notes. 2P has 4 notes. Diff = 0.
    
    print(f"Alt Cost Mean: {np.mean(metrics['alt_cost']):.2f}")
    
    # Let's check specific window values if possible, but mean is enough for now.
    
    print("\nVerification Complete.")

if __name__ == "__main__":
    verify_dp()
