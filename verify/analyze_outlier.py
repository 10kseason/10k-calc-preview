import bms_parser
import metric_calc
import calc
import os
import numpy as np

def analyze_outlier():
    file_path = r"d:\계산기\테스트 샘플\10Key-Revive-pack\[削除 feat. Nikki Simmons] Destr0yer\1010INSANE.bml"
    
    print(f"Analyzing {os.path.basename(file_path)}...")
    
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        parser = bms_parser.BMSParser(file_path)
        notes = parser.parse()
        
    print(f"Total Notes: {len(notes)}")
    if not notes:
        return
        
    duration = notes[-1]['time'] - notes[0]['time']
    print(f"Duration: {duration:.2f}s")
    
    columns = [n['column'] for n in notes]
    keys = max(columns) + 1
    print(f"Keys: {keys}")
    
    print("First 10 notes:")
    for n in notes[:10]:
        print(n)
        
    # Metrics
    metrics = metric_calc.calculate_metrics(notes, duration)
    
    print("\n=== Metrics Analysis ===")
    print(f"Max NPS: {np.max(metrics['nps']):.2f}")
    print(f"Avg NPS: {np.mean(metrics['nps']):.2f}")
    print(f"Max LN Strain: {np.max(metrics['ln_strain']):.2f}")
    print(f"Max Jack Pen: {np.max(metrics['jack_pen']):.2f}")
    print(f"Max Roll Pen: {np.max(metrics['roll_pen']):.2f}")
    print(f"Max Alt Cost: {np.max(metrics['alt_cost']):.2f}")
    print(f"Max Hand Strain: {np.max(metrics['hand_strain']):.2f}")
    
    # Calculation with Tuned Weights
    # alpha (NPS): 1.0 -> 0.8
    # theta (Hand): 1.0 -> 0.5
    # eta (Alt): 1.0 -> 0.5
    res = calc.compute_map_difficulty(
        metrics['nps'], metrics['ln_strain'], metrics['jack_pen'], 
        metrics['roll_pen'], metrics['alt_cost'], metrics['hand_strain'],
        alpha=0.8, theta=0.5, eta=0.5,
        duration=duration,
        total_notes=len(notes),
        uncap_level=True
    )
    
    print("\n=== Difficulty Result ===")
    print(f"b_t (Window Load) Peak: {np.max(res['b_t']):.2f}")
    print(f"b_t (Window Load) Mean: {np.mean(res['b_t']):.2f}")
    print(f"Endurance (F): {res['F']:.2f}")
    print(f"Burst (P): {res['P']:.2f}")
    print(f"D0 (Raw): {res['D0']:.2f}")
    print(f"Est Level: {res['est_level']}")
    print(f"Length Bonus: {res.get('length_bonus', 1.0):.2f}")

if __name__ == "__main__":
    analyze_outlier()
