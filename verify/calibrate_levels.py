import json
import numpy as np
from scipy.optimize import minimize
import matplotlib.pyplot as plt

# Configuration
DATA_PATH = r"d:\계산기\analysis_results_calibration.jsonl"
OUTPUT_JSON = r"d:\계산기\calibration_results.json"

def load_data():
    """Loads (D_raw, Label) pairs from the calibration dataset."""
    d_vals = []
    l_vals = []
    
    print(f"Loading data from {DATA_PATH}...")
    with open(DATA_PATH, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                entry = json.loads(line)
                d = entry['d_raw']
                l = entry['label']
                
                if d > 0 and l > 0:
                    # User Request: Exclude GCS levels >= 25
                    # Assuming all data in this file is relevant, but let's just filter globally for now
                    # as 10k2s doesn't go that high usually.
                    if l >= 25:
                        continue
                        
                    d_vals.append(d)
                    l_vals.append(l)
            except Exception:
                continue
                
    return np.array(d_vals), np.array(l_vals)

def mapping_function(D, D_min, D_max, gamma):
    """
    L = 1 + 24 * ((D - D_min) / (D_max - D_min)) ** gamma
    """
    # Avoid division by zero
    if D_max <= D_min:
        return np.ones_like(D)
    
    # Normalize
    norm_D = (D - D_min) / (D_max - D_min)
    norm_D = np.maximum(0, norm_D) # Clamp negative to 0
    
    return 1 + 24 * (norm_D ** gamma)

def objective_function(params, D_vals, L_true):
    D_min, D_max, gamma = params
    
    # Constraints
    if D_min >= D_max: return 1e9
    if gamma <= 0: return 1e9
    if D_min < 0: return 1e9 # D_min shouldn't be negative usually
    
    L_pred = mapping_function(D_vals, D_min, D_max, gamma)
    
    # MSE
    mse = np.mean((L_pred - L_true) ** 2)
    return mse

def calibrate():
    D_vals, L_true = load_data()
    
    if len(D_vals) == 0:
        print("No data found!")
        return

    print(f"Loaded {len(D_vals)} data points.")
    print(f"D range: {np.min(D_vals):.2f} - {np.max(D_vals):.2f}")
    print(f"L range: {np.min(L_true)} - {np.max(L_true)}")

    # Initial Guess
    # D_min: somewhat below min D for level 1
    # D_max: somewhat above max D for level 25
    # gamma: 1.0
    
    # Heuristic initialization
    # Find D corresponding to min/max levels
    min_L_idx = np.argmin(L_true)
    max_L_idx = np.argmax(L_true)
    
    init_D_min = np.min(D_vals) * 0.5
    init_D_max = np.max(D_vals)
    init_gamma = 1.0
    
    initial_params = [init_D_min, init_D_max, init_gamma]
    print(f"Initial params: {initial_params}")
    
    # Optimization
    result = minimize(
        objective_function, 
        initial_params, 
        args=(D_vals, L_true),
        method='Nelder-Mead',
        tol=1e-5
    )
    
    opt_D_min, opt_D_max, opt_gamma = result.x
    
    print("\nOptimization Complete!")
    print(f"Success: {result.success}")
    print(f"Message: {result.message}")
    print(f"Optimized Parameters:")
    print(f"  D_min: {opt_D_min:.4f}")
    print(f"  D_max: {opt_D_max:.4f}")
    print(f"  gamma: {opt_gamma:.4f}")
    
    # Evaluation
    L_pred = mapping_function(D_vals, opt_D_min, opt_D_max, opt_gamma)
    mse = np.mean((L_pred - L_true) ** 2)
    mae = np.mean(np.abs(L_pred - L_true))
    
    print(f"\nMetrics:")
    print(f"  MSE: {mse:.4f}")
    print(f"  MAE: {mae:.4f}")
    
    # Save results
    calibration_results = {
        "D_min": opt_D_min,
        "D_max": opt_D_max,
        "gamma": opt_gamma,
        "metrics": {
            "mse": mse,
            "mae": mae
        }
    }
    
    with open(OUTPUT_JSON, "w", encoding='utf-8') as f:
        json.dump(calibration_results, f, indent=4)
    print(f"\nResults saved to {OUTPUT_JSON}")

if __name__ == "__main__":
    calibrate()
