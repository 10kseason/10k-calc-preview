import bms_parser
import osu_parser
import metric_calc
import calc
import numpy as np

def compare_charts():
    bms_path = r"d:\계산기\문제분석용\debug.bms"
    osu_path = r"d:\계산기\문제분석용\Collection - Piano Beatmap Set (CircusGalop) [10K HELL CIRCUS].osu"
    
    print(f"--- Comparing BMS vs OSU ---")
    
    # 1. Parse BMS
    print("\n[BMS Parsing]")
    bms_p = bms_parser.BMSParser(bms_path)
    bms_notes = bms_p.parse()
    print(f"BMS Notes: {len(bms_notes)}")
    print(f"BMS Duration: {bms_p.duration:.4f}s")
    
    # 2. Parse OSU
    print("\n[OSU Parsing]")
    osu_p = osu_parser.OsuParser(osu_path)
    osu_notes = osu_p.parse()
    print(f"OSU Notes: {len(osu_notes)}")
    print(f"OSU Duration: {osu_p.duration:.4f}s")
    
    # 3. Compare Notes
    print("\n[Note Comparison]")
    min_len = min(len(bms_notes), len(osu_notes))
    diff_count = 0
    for i in range(min_len):
        b = bms_notes[i]
        o = osu_notes[i]
        
        # Check Time, Column, Type
        t_diff = abs(b['time'] - o['time'])
        c_diff = b['column'] != o['column']
        type_diff = b['type'] != o['type']
        
        if t_diff > 0.001 or c_diff or type_diff:
            print(f"Diff at Index {i}:")
            print(f"  BMS: {b}")
            print(f"  OSU: {o}")
            diff_count += 1
            if diff_count > 5:
                print("  ... (Stopping note diff log)")
                break
                
    if len(bms_notes) != len(osu_notes):
        print(f"Note Count Mismatch! BMS={len(bms_notes)}, OSU={len(osu_notes)}")
        
    # 4. Compare Metrics
    print("\n[Metric Comparison]")
    bms_m = metric_calc.calculate_metrics(bms_notes, bms_p.duration)
    osu_m = metric_calc.calculate_metrics(osu_notes, osu_p.duration)
    
    for key in bms_m:
        b_val = np.mean(bms_m[key])
        o_val = np.mean(osu_m[key])
        print(f"{key:12s} | BMS: {b_val:.4f} | OSU: {o_val:.4f} | Diff: {abs(b_val-o_val):.4f}")

    # 5. Compare D0
    print("\n[Difficulty Comparison]")
    # Use default params for comparison
    bms_res = calc.compute_map_difficulty(
        bms_m['nps'], bms_m['ln_strain'], bms_m['jack_pen'], 
        bms_m['roll_pen'], bms_m['alt_cost'], bms_m['hand_strain'], bms_m['chord_strain'],
        duration=bms_p.duration, total_notes=len(bms_notes), uncap_level=True, D_max=110.0
    )
    osu_res = calc.compute_map_difficulty(
        osu_m['nps'], osu_m['ln_strain'], osu_m['jack_pen'], 
        osu_m['roll_pen'], osu_m['alt_cost'], osu_m['hand_strain'], osu_m['chord_strain'],
        duration=osu_p.duration, total_notes=len(osu_notes), uncap_level=True, D_max=110.0
    )
    
    print(f"BMS D0: {bms_res['D0']:.4f} -> Level: {bms_res['pattern_level']:.2f}")
    print(f"OSU D0: {osu_res['D0']:.4f} -> Level: {osu_res['pattern_level']:.2f}")

if __name__ == "__main__":
    compare_charts()
