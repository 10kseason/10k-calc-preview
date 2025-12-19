import osu_parser
import metric_calc
import numpy as np

def verify_osu():
    print("Verifying Osu Parser...")
    
    # 1. Test Parser
    print("\n[1] Testing Parser with .osu file...")
    parser = osu_parser.OsuParser("d:/계산기/test_sample.osu")
    notes = parser.parse()
    print(f"Parsed {len(notes)} notes.")
    print(f"KeyCount: {parser.key_count}")
    print(f"Duration: {parser.duration:.2f}s")
    
    if len(notes) != 5:
        print(f"FAIL: Expected 5 notes, got {len(notes)}")
        return
        
    # Check Note Types
    # 4 Normal notes, 1 LN
    ln_count = sum(1 for n in notes if n['type'] == 'ln')
    if ln_count != 1:
        print(f"FAIL: Expected 1 LN, got {ln_count}")
        return
        
    print("PASS: Note counts correct.")
    
    # 2. Test Metric Calc
    print("\n[2] Testing Metric Calculation...")
    metrics = metric_calc.calculate_metrics(notes, parser.duration)
    print(f"NPS Mean: {np.mean(metrics['nps']):.2f}")
    
    print("\nVerification Complete.")

if __name__ == "__main__":
    verify_osu()
