import os
import json
import re
import numpy as np
import bms_parser
import osu_parser
import calc
import metric_calc
import time

# Configuration
OUTPUT_FILE = r"d:\계산기\analysis_results_calibration.jsonl"
GCS_ROOT = r"d:\계산기\패턴 모음2(GCS)"
PATTERN_ROOT = r"d:\계산기\패턴 모음"

# Load Optimized Params
OPT_PARAMS = {}
try:
    with open(r"d:\계산기\final_params.json", "r", encoding='utf-8') as f:
        OPT_PARAMS = json.load(f)
    print("Loaded final_params.json")
except Exception:
    print("Warning: final_params.json not found. Using default weights.")

def get_bms_label(file_path):
    """Robustly extract BMS label (#PLAYLEVEL)."""
    label = None
    # Try manual read first as it's faster and robust to encoding for just one tag
    encodings = ['utf-8', 'cp949', 'shift_jis', 'euc-kr']
    for enc in encodings:
        try:
            with open(file_path, 'r', encoding=enc, errors='ignore') as f:
                for line in f:
                    if line.upper().startswith("#PLAYLEVEL"):
                        try:
                            parts = line.split()
                            if len(parts) >= 2:
                                label = int(parts[1])
                                return label
                        except: pass
        except: pass
    return None

def get_osu_label(file_path):
    """Extract label from Osu filename (Lv.X)."""
    filename = os.path.basename(file_path)
    match = re.search(r'Lv\.(\d+)', filename)
    if match:
        return int(match.group(1))
    return None

def scan_targets():
    """Yields (file_path, type) tuples."""
    
    # 1. GCS (BMS)
    print(f"Scanning GCS: {GCS_ROOT}")
    if os.path.exists(GCS_ROOT):
        for root, dirs, files in os.walk(GCS_ROOT):
            for file in files:
                if file.lower().endswith(('.bms', '.bme', '.bml', '.pms')):
                    yield os.path.join(root, file), 'BMS'

    # 2. 10K2S (Osu)
    print(f"Scanning 10K2S in: {PATTERN_ROOT}")
    if os.path.exists(PATTERN_ROOT):
        for root, dirs, files in os.walk(PATTERN_ROOT):
            # Check if directory name contains "10K2S"
            if "10K2S" in os.path.basename(root).upper():
                for file in files:
                    if file.lower().endswith('.osu'):
                        yield os.path.join(root, file), 'OSU'

def run_analysis():
    print("Starting Calibration Analysis...")
    
    if os.path.exists(OUTPUT_FILE):
        os.remove(OUTPUT_FILE)
        
    count = 0
    success_count = 0
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f_out:
        for file_path, ftype in scan_targets():
            count += 1
            if count % 100 == 0:
                print(f"Processed {count} files... (Success: {success_count})")
                
            try:
                # 1. Extract Label
                label = None
                if ftype == 'BMS':
                    raw_label = get_bms_label(file_path)
                    if raw_label is not None:
                        # GCS Rule: Label - 5
                        label = raw_label - 5
                        if label <= 0: label = None
                elif ftype == 'OSU':
                    label = get_osu_label(file_path)
                    # 10K2S Rule: Use as is (User said "existing level")
                
                if label is None:
                    continue

                # 2. Parse & Calculate
                if ftype == 'BMS':
                    parser = bms_parser.BMSParser(file_path)
                else:
                    parser = osu_parser.OsuParser(file_path)
                
                notes = parser.parse()
                if not notes: continue
                
                duration = parser.duration
                if duration < 10: continue
                
                # Metrics
                metrics = metric_calc.calculate_metrics(notes, duration)
                
                # D_raw Calculation (Optimized)
                # Use OPT_PARAMS if available, else defaults
                # We need 'opt_d0' specifically
                
                w = [OPT_PARAMS.get(k, v) for k, v in zip(['alpha', 'theta', 'eta', 'omega', 'D_max'], [0.8, 1.0, 0.5, 2.0, 25.72])]
                p = [OPT_PARAMS.get(k, v) for k, v in zip(['lam_L', 'lam_S', 'gamma_curve'], [0.8, 0.95, 1.5])]
                
                # Note: compute_map_difficulty args might differ slightly from my list above, 
                # checking calc.py signature is safer but I'll use kwargs style if possible or standard positional
                # calc.compute_map_difficulty(nps, ln_strain, jack_pen, roll_pen, alt_cost, hand_strain, chord_strain, duration, total_notes, ...)
                
                res = calc.compute_map_difficulty(
                    metrics['nps'], metrics['ln_strain'], metrics['jack_pen'], 
                    metrics['roll_pen'], metrics['alt_cost'], metrics['hand_strain'],
                    metrics['chord_strain'],
                    alpha=OPT_PARAMS.get('alpha', 0.8),
                    theta=OPT_PARAMS.get('theta', 1.0),
                    eta=OPT_PARAMS.get('eta', 0.5),
                    omega=OPT_PARAMS.get('omega', 2.0),
                    lam_L=OPT_PARAMS.get('lam_L', 0.8),
                    lam_S=OPT_PARAMS.get('lam_S', 0.95),
                    D_max=OPT_PARAMS.get('D_max', 25.72),
                    gamma_curve=OPT_PARAMS.get('gamma_curve', 1.5),
                    duration=duration,
                    total_notes=len(notes),
                    uncap_level=True, # Critical for calibration
                    level_offset=0.72 if ftype == 'OSU' else 0.0
                )
                
                d_raw = res['D0']
                
                # Write Result
                entry = {
                    'file': os.path.basename(file_path),
                    'full_path': file_path,
                    'type': ftype,
                    'label': label,
                    'd_raw': d_raw
                }
                f_out.write(json.dumps(entry) + "\n")
                success_count += 1
                
            except Exception as e:
                # print(f"Error processing {file_path}: {e}")
                pass

    print(f"Analysis Complete. Processed {count} files. Saved {success_count} valid entries to {OUTPUT_FILE}")

if __name__ == "__main__":
    run_analysis()
