import json
import numpy as np
import matplotlib.pyplot as plt

import calc

# Configuration
DATA_PATH = r"d:\계산기\analysis_results_calibration.jsonl"
PARAMS_PATH = r"d:\계산기\final_params.json"

def load_data():
    d_vals = []
    l_vals = []
    files = []
    
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
                    files.append(entry['file'])
            except: continue
    return np.array(d_vals), np.array(l_vals), files

def get_predicted_level(D, D_min, D_max, gamma):
    # Use calc.py's logic which now includes Band-wise Correction
    return calc.pattern_level_from_D0(D, D_min, D_max, gamma, uncap=False)

def analyze():
    # Load Params
    with open(PARAMS_PATH, 'r') as f:
        params = json.load(f)
    
    D_min = params.get('D_min', 0)
    D_max = params.get('D_max', 25.72)
    gamma = params.get('gamma_curve', 1.0)
    
    print(f"Using Params: D_min={D_min:.2f}, D_max={D_max:.2f}, gamma={gamma:.2f}")
    
    # Load Data
    D_vals, L_true, files = load_data()
    
    # Predict (Scalar loop)
    L_pred = []
    for d in D_vals:
        L_pred.append(get_predicted_level(d, D_min, D_max, gamma))
    L_pred = np.array(L_pred)
    
    # Residuals
    residuals = L_pred - L_true
    
    # Binning by True Level
    bins = np.arange(1, 27)
    bin_means = []
    bin_stds = []
    bin_counts = []
    
    print("\n--- Residual Analysis by Level ---")
    print(f"{'Level':<5} | {'Count':<5} | {'Mean Res':<10} | {'Std Res':<10} | {'MAE':<10}")
    print("-" * 55)
    
    for b in bins:
        mask = (L_true == b)
        if np.any(mask):
            res_bin = residuals[mask]
            mean_res = np.mean(res_bin)
            std_res = np.std(res_bin)
            mae_bin = np.mean(np.abs(res_bin))
            
            bin_means.append(mean_res)
            bin_stds.append(std_res)
            bin_counts.append(len(res_bin))
            
            print(f"{b:<5} | {len(res_bin):<5} | {mean_res:<10.2f} | {std_res:<10.2f} | {mae_bin:<10.2f}")
        else:
            bin_means.append(0)
            bin_stds.append(0)
            bin_counts.append(0)
            
    # Check High Level Correlation
    high_level_data = []
    print("\n--- High Level Data Points (Label > 18) ---")
    print(f"{'Label':<5} | {'D_raw':<10} | {'Pred':<10}")
    for d, l in zip(D_vals, L_true):
        if l > 18:
            pred = get_predicted_level(d, D_min, D_max, gamma)
            high_level_data.append({
                "label": int(l),
                "d_raw": float(d),
                "pred": float(pred)
            })
            print(f"{l:<5} | {d:<10.2f} | {pred:<10.2f}")
            
    with open(r"d:\계산기\high_level_data.json", "w", encoding='utf-8') as f:
        json.dump(high_level_data, f, indent=4)
    print("Saved high level data to d:\\계산기\\high_level_data.json")

    # Overall Metrics
    mse = np.mean(residuals ** 2)
    mae = np.mean(np.abs(residuals))

    # Save Residuals to JSON
    residual_data = {
        "overall_mse": mse,
        "overall_mae": mae,
        "by_level": []
    }
    
    for b in bins:
        mask = (L_true == b)
        if np.any(mask):
            res_bin = residuals[mask]
            residual_data["by_level"].append({
                "level": int(b),
                "count": int(len(res_bin)),
                "mean_res": float(np.mean(res_bin)),
                "std_res": float(np.std(res_bin)),
                "mae": float(np.mean(np.abs(res_bin)))
            })
            
    with open(r"d:\계산기\residuals.json", "w", encoding='utf-8') as f:
        json.dump(residual_data, f, indent=4)
    print("Saved residuals to d:\\계산기\\residuals.json")

    print("-" * 55)
    print(f"Overall MSE: {mse:.4f}")
    print(f"Overall MAE: {mae:.4f}")

if __name__ == "__main__":
    analyze()
