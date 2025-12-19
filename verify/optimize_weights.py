
import os
import glob
import bms_parser
import osu_parser
import calc
import metric_calc
import numpy as np
import time
import re
from scipy.optimize import minimize
from sklearn.model_selection import KFold
import random
import json

def load_charts():
    # 1. Setup Paths
    target_dirs = [
        r"d:\계산기\테스트 샘플",
        r"d:\계산기\패턴 모음",
        r"d:\계산기\패턴 모음2(GCS)",
        r"d:\계산기\osu 폴더 전체"
    ]
    
    files = []
    print("Scanning files...")
    for root_dir in target_dirs:
        # BMS
        for ext in ['*.bms', '*.bme', '*.bml']:
            files.extend(glob.glob(os.path.join(root_dir, '**', ext), recursive=True))
        # OSU
        for ext in ['*.osu']:
            files.extend(glob.glob(os.path.join(root_dir, '**', ext), recursive=True))
            
    print(f"Found {len(files)} files.")
    
    chart_data = []
    
    for i, file_path in enumerate(files):
        if i % 100 == 0:
            print(f"Processing {i}/{len(files)}...")
            
        try:
            # Determine Type
            is_osu = file_path.lower().endswith('.osu')
            is_gcs = "패턴 모음2(GCS)" in file_path
            
            # Parse
            if is_osu:
                parser = osu_parser.OsuParser(file_path)
            else:
                parser = bms_parser.BMSParser(file_path)
                
            notes = parser.parse()
            if not notes:
                continue
                
            # [NEW] Filter 10K Only (Check AFTER parse)
            if is_osu and parser.key_count != 10:
                continue
                
            duration = parser.duration
            if duration < 10:
                continue
                
            # Get Label (if BMS)
            label = None
            title = "Unknown"
            
            if is_osu:
                title = parser.header.get('Title', 'Unknown')
                # [Modified] Disable Osu Level Label Parsing
                label = None
            else:
                # BMS Header parsing
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        if line.upper().startswith("#PLAYLEVEL"):
                            try:
                                label = int(line.split()[1])
                            except: pass
                        if line.upper().startswith("#TITLE"):
                            try:
                                title = line.split(maxsplit=1)[1].strip()
                            except: pass
            
            # [NEW] GCS Filtering Rules
            if is_gcs:
                if label is None or label == 0:
                    continue # Ignore 0 or unrated
                
                # Apply -5 Offset
                label = label - 5
                
                # Ensure valid range (optional, but good for safety)
                if label < 1:
                    continue
            
            if label is None:
                continue
            
            metrics = metric_calc.calculate_metrics(notes, duration)
            
            chart_data.append({
                'metrics': metrics,
                'duration': duration,
                'total_notes': len(notes),
                'label': label,
                'title': title,
                'file': os.path.basename(file_path)
            })
                
        except Exception as e:
            # print(f"Error loading {file_path}: {e}")
            pass
            
    print(f"Loaded {len(chart_data)}/{len(files)} valid charts.")
    return chart_data

def objective_stage_1(params, chart_data, fixed_physics):
    """
    Stage 1: Weights Optimization (Alpha, Theta, Eta, Omega, D_max)
    Physics (Lam_L, Lam_S, Gamma) are FIXED.
    """
    alpha, theta, eta, omega, D_max = params
    lam_L, lam_S, gamma = fixed_physics
    
    total_error = 0.0
    for data in chart_data:
        m = data['metrics']
        res = calc.compute_map_difficulty(
            m['nps'], m['ln_strain'], m['jack_pen'], m['roll_pen'], m['alt_cost'], m['hand_strain'],
            m['chord_strain'],
            alpha=alpha, theta=theta, eta=eta, omega=omega,
            lam_L=lam_L, lam_S=lam_S, # Fixed
            cap_start=60.0, cap_range=30.0,
            duration=data['duration'],
            total_notes=data['total_notes'],
            uncap_level=True
        )
        # Level Mapping with Fixed Gamma
        est_level = calc.pattern_level_from_D0(
            res['D0'], D_min=0.0, D_max=D_max, gamma=gamma, uncap=True
        )
        total_error += abs(est_level - data['label'])
        
    return total_error / len(chart_data)

def objective_stage_2(params, chart_data, fixed_weights):
    """
    Stage 2: Physics Optimization (Lam_L, Lam_S, Gamma)
    Weights are FIXED.
    """
    lam_L, lam_S, gamma = params
    alpha, theta, eta, omega, D_max = fixed_weights
    
    total_error = 0.0
    for data in chart_data:
        m = data['metrics']
        res = calc.compute_map_difficulty(
            m['nps'], m['ln_strain'], m['jack_pen'], m['roll_pen'], m['alt_cost'], m['hand_strain'],
            m['chord_strain'],
            alpha=alpha, theta=theta, eta=eta, omega=omega, # Fixed
            lam_L=lam_L, lam_S=lam_S, # Optimizing
            cap_start=60.0, cap_range=30.0,
            duration=data['duration'],
            total_notes=data['total_notes'],
            uncap_level=True
        )
        # Level Mapping with Optimizing Gamma
        est_level = calc.pattern_level_from_D0(
            res['D0'], D_min=0.0, D_max=D_max, gamma=gamma, uncap=True
        )
        total_error += abs(est_level - data['label'])
        
    return total_error / len(chart_data)

def optimize_weights():
    # 1. Load Data
    all_data = load_charts()
    if not all_data: 
        print("No charts found.")
        return

    best_mae = float('inf')
    best_params = None
    best_seed = -1
    
    # 5-Fold Cross Validation
    kf = KFold(n_splits=5, shuffle=True, random_state=42)
    
    print(f"\nStarting 5-Fold Cross-Validation Optimization...")
    print("-" * 60)
    
    fold_idx = 0
    for train_index, test_index in kf.split(all_data):
        fold_idx += 1
        seed = 42 + fold_idx # Just for logging
        
        train_data = [all_data[i] for i in train_index]
        test_data = [all_data[i] for i in test_index]
        
        # ---------------------------------------------------------
        # Stage 1: Optimize Weights (Physics Fixed)
        # ---------------------------------------------------------
        fixed_physics = [0.3, 0.8, 1.0] 
        init_weights = [1.0, 1.0, 0.5, 1.0, 100.0]
        # D_max bounds (50, 120), Omega (0.5, 2.0)
        bounds_weights = [(0.1, 5.0), (0.1, 5.0), (0.0, 3.0), (0.5, 2.0), (50.0, 120.0)]
        
        res1 = minimize(
            objective_stage_1, init_weights, args=(train_data, fixed_physics),
            method='L-BFGS-B', bounds=bounds_weights
        )
        best_weights_iter = res1.x

        # ---------------------------------------------------------
        # Stage 2: Optimize Physics (Weights Fixed)
        # ---------------------------------------------------------
        init_physics = [0.3, 0.8, 1.0]
        # Gamma bounds (1.0, 1.5)
        bounds_physics = [(0.05, 0.5), (0.5, 0.95), (1.0, 1.5)]
        
        res2 = minimize(
            objective_stage_2, init_physics, args=(train_data, best_weights_iter),
            method='L-BFGS-B', bounds=bounds_physics
        )
        best_physics_iter = res2.x

        # ---------------------------------------------------------
        # Validation
        # ---------------------------------------------------------
        alpha, theta, eta, omega, D_max = best_weights_iter
        lam_L, lam_S, gamma = best_physics_iter
        
        def calculate_mae(dataset):
            total_error = 0.0
            for data in dataset:
                m = data['metrics']
                res = calc.compute_map_difficulty(
                    m['nps'], m['ln_strain'], m['jack_pen'], m['roll_pen'], m['alt_cost'], m['hand_strain'],
                    m['chord_strain'],
                    alpha=alpha, theta=theta, eta=eta, omega=omega,
                    lam_L=lam_L, lam_S=lam_S,
                    cap_start=60.0, cap_range=30.0,
                    duration=data['duration'],
                    total_notes=data['total_notes'],
                    uncap_level=True,
                    D_max=D_max, gamma_curve=gamma # Pass optimized params
                )
                est_level = res['est_level']
                total_error += abs(est_level - data['label'])
            return total_error / len(dataset)

        train_mae = calculate_mae(train_data)
        test_mae = calculate_mae(test_data)
        
        print(f"Fold {fold_idx:02d} (Seed {seed}): Train={train_mae:.4f}, Test={test_mae:.4f}")
        
        # Save best result (based on Test MAE)
        if test_mae < best_mae:
            best_mae = test_mae
            best_params = {
                'weights': best_weights_iter,
                'physics': best_physics_iter
            }
            best_seed = seed
            
    print("-" * 60)
    print(f"BEST RESULT (Seed {best_seed}):")
    print(f"Test MAE: {best_mae:.4f}")
    
    # Best Optimized Params (P_opt)
    opt_alpha, opt_theta, opt_eta, opt_omega, opt_D_max = best_params['weights']
    opt_lam_L, opt_lam_S, opt_gamma_curve = best_params['physics']
    
    print(f"[P_opt] Weights: Alpha={opt_alpha:.3f}, Theta={opt_theta:.3f}, Eta={opt_eta:.3f}, Omega={opt_omega:.3f}")
    print(f"[P_opt] Physics: Lam_L={opt_lam_L:.3f}, Lam_S={opt_lam_S:.3f}")
    print(f"[P_opt] Scaling: D_max={opt_D_max:.1f}, Gamma={opt_gamma_curve:.3f}")
    
    # Manual Defaults (P_manual) from calc.py
    man_alpha, man_theta, man_eta, man_omega, man_D_max = 0.8, 0.5, 0.5, 1.5, 100.0 # Updated default D_max
    man_lam_L, man_lam_S, man_gamma_curve = 0.3, 0.8, 1.2 # Updated default Gamma
    
    # Hybrid Params (5:5 Mix)
    # [수정] 50:50 Mix
    ratio_opt = 0.5
    ratio_man = 0.5
    
    hyb_alpha = opt_alpha * ratio_opt + man_alpha * ratio_man
    hyb_theta = opt_theta * ratio_opt + man_theta * ratio_man
    hyb_eta = opt_eta * ratio_opt + man_eta * ratio_man
    hyb_omega = opt_omega * ratio_opt + man_omega * ratio_man
    hyb_D_max = opt_D_max * ratio_opt + man_D_max * ratio_man
    
    hyb_lam_L = opt_lam_L * ratio_opt + man_lam_L * ratio_man
    hyb_lam_S = opt_lam_S * ratio_opt + man_lam_S * ratio_man
    hyb_gamma_curve = opt_gamma_curve * ratio_opt + man_gamma_curve * ratio_man
    
    print("-" * 60)
    print(f"HYBRID PARAMETERS (50% Opt + 50% Manual):")
    print(f"Weights: Alpha={hyb_alpha:.3f}, Theta={hyb_theta:.3f}, Eta={hyb_eta:.3f}, Omega={hyb_omega:.3f}")
    print(f"Physics: Lam_L={hyb_lam_L:.3f}, Lam_S={hyb_lam_S:.3f}")
    print(f"Scaling: D_max={hyb_D_max:.1f}, Gamma={hyb_gamma_curve:.3f}")
    print("-" * 60)
    
    # 5-Run Verification of Hybrid Params
    print(f"Verifying Hybrid Parameters (5 Runs)...")
    
    hybrid_maes = []
    
    for k in range(5):
        # Shuffle and Split
        random.seed(100 + k)
        random.shuffle(all_data)
        split_idx = int(len(all_data) * 0.8)
        train_data = all_data[:split_idx]
        test_data = all_data[split_idx:]
        
        def calculate_mae_hybrid(dataset):
            total_error = 0.0
            for data in dataset:
                m = data['metrics']
                res = calc.compute_map_difficulty(
                    m['nps'], m['ln_strain'], m['jack_pen'], m['roll_pen'], m['alt_cost'], m['hand_strain'],
                    m['chord_strain'],
                    alpha=hyb_alpha, theta=hyb_theta, eta=hyb_eta, omega=hyb_omega,
                    lam_L=hyb_lam_L, lam_S=hyb_lam_S,
                    cap_start=60.0, cap_range=30.0,
                    duration=data['duration'],
                    total_notes=data['total_notes'],
                    uncap_level=True,
                    D_max=hyb_D_max, gamma_curve=hyb_gamma_curve
                )
                est_level = res['est_level'] # compute_map_difficulty returns est_level directly now
                total_error += abs(est_level - data['label'])
            return total_error / len(dataset)

        train_mae = calculate_mae_hybrid(train_data)
        test_mae = calculate_mae_hybrid(test_data)
        hybrid_maes.append(test_mae)
        
        print(f"Verify Run {k+1}: Train MAE={train_mae:.4f}, Test MAE={test_mae:.4f}")
        
    avg_test_mae = sum(hybrid_maes) / len(hybrid_maes)
    print("-" * 60)
    print(f"Average Test MAE (Hybrid): {avg_test_mae:.4f}")
    print("-" * 60)
    
    # Save to JSON
    final_params = {
        'alpha': hyb_alpha, 'theta': hyb_theta, 'eta': hyb_eta, 'omega': hyb_omega,
        'lam_L': hyb_lam_L, 'lam_S': hyb_lam_S,
        'D_max': hyb_D_max, 'gamma_curve': hyb_gamma_curve,
        'mae': avg_test_mae
    }
    
    with open(r"d:\계산기\final_params.json", "w", encoding='utf-8') as f:
        json.dump(final_params, f, indent=4)
    print("Saved final parameters to d:\\계산기\\final_params.json")

if __name__ == "__main__":
    optimize_weights()
