import json
import numpy as np
import matplotlib.pyplot as plt

# Configuration
DATA_PATH = r"d:\계산기\analysis_results_calibration.jsonl"
PARAMS_PATH = r"d:\계산기\final_params.json"

def load_data():
    d_vals = []
    l_vals = []
    with open(DATA_PATH, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                entry = json.loads(line)
                d = entry['d_raw']
                l = entry['label']
                if d > 0 and l > 0:
                    if l >= 25: continue
                    d_vals.append(d)
                    l_vals.append(l)
            except: continue
    return np.array(d_vals), np.array(l_vals)

def base_mapping(D, D_min, D_max, gamma):
    if D_max <= D_min: return np.ones_like(D)
    norm_D = (D - D_min) / (D_max - D_min)
    norm_D = np.maximum(0, norm_D)
    return 1 + 24 * (norm_D ** gamma)

def apply_correction(L_pred):
    """
    Band-wise Level Correction (Attempt 4):
    - Low (< 12): -1.5
    - Trans (12-13): -1.5 -> 0.0
    - Trans (13-13.5): 0.0 -> +1.5 (Steep ramp)
    - High (13.5-16): +1.5
    - Trans (16-18): +1.5 -> +5.0
    - Top (> 18): +5.0
    """
    L_corr = np.copy(L_pred)
    
    for i, l in enumerate(L_pred):
        if l < 12.0:
            L_corr[i] = max(1.0, l - 1.5)
        elif l < 13.0:
            # Transition -1.5 -> 0.0
            t = l - 12.0
            L_corr[i] = l - 1.5 * (1.0 - t)
        elif l < 13.5:
            # Transition 0.0 -> +1.5 (Steep)
            t = (l - 13.0) / 0.5
            L_corr[i] = l + 1.5 * t
        elif l < 16.0:
            L_corr[i] = l + 1.5
        elif l < 18.0:
            # Transition +1.5 -> +5.0
            t = (l - 16.0) / 2.0
            L_corr[i] = l + 1.5 + (3.5 * t)
        else:
            L_corr[i] = l + 5.0
            
    return L_corr

def test_correction():
    # Load Params
    with open(PARAMS_PATH, 'r') as f:
        params = json.load(f)
    
    D_min = params.get('D_min', 0)
    D_max = params.get('D_max', 25.72)
    gamma = params.get('gamma_curve', 1.0)
    
    D_vals, L_true = load_data()
    
    # Base Prediction
    L_base = base_mapping(D_vals, D_min, D_max, gamma)
    mae_base = np.mean(np.abs(L_base - L_true))
    
    # Corrected Prediction
    L_corr = apply_correction(L_base)
    mae_corr = np.mean(np.abs(L_corr - L_true))
    
    print(f"Base MAE: {mae_base:.4f}")
    print(f"Corrected MAE: {mae_corr:.4f}")
    
    # Show improvement by level
    bins = np.arange(1, 27)
    print("\nLevel | Count | Base Res | Corr Res")
    for b in bins:
        mask = (L_true == b)
        if np.any(mask):
            base_res = np.mean(L_base[mask] - L_true[mask])
            corr_res = np.mean(L_corr[mask] - L_true[mask])
            print(f"{b:<5} | {np.sum(mask):<5} | {base_res:<8.2f} | {corr_res:<8.2f}")

if __name__ == "__main__":
    test_correction()
