
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

# --- Configuration ---
TIERS = [
    (1, 5, "Beginner"),
    (5, 10, "Novice"),
    (10, 12, "Intermediate"),
    (12, 14, "Advanced"),
    (14, 16, "Expert"),
    (16, 999, "Master") # 16+
]

def load_charts():
    # 1. Setup Paths (Restricted to Labeled BMS)
    target_dirs = [
        r"d:\계산기\테스트 샘플",
        r"d:\계산기\패턴 모음2(GCS)"
    ]
    
    files = []
    print("Scanning files...")
    for root_dir in target_dirs:
        # BMS
        for ext in ['*.bms', '*.bme', '*.bml']:
            files.extend(glob.glob(os.path.join(root_dir, '**', ext), recursive=True))
        # OSU (Only if mixed in these folders, though usually BMS folders contain BMS)
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
                
            # Filter 10K Only
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
            
            # GCS Filtering Rules
            if is_gcs:
                if label is None or label == 0:
                    continue # Ignore 0 or unrated
                
                # Apply -5 Offset
                label = label - 5
                
                # Ensure valid range
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
            pass
            
    print(f"Loaded {len(chart_data)}/{len(files)} valid labeled charts.")
    return chart_data

def objective_stage_1(params, chart_data, fixed_physics):
    """Stage 1: Weights Optimization"""
    alpha, theta, eta, omega, D_max = params
    lam_L, lam_S, gamma = fixed_physics
    
    total_error = 0.0
    for data in chart_data:
        m = data['metrics']
        res = calc.compute_map_difficulty(
            m['nps'], m['ln_strain'], m['jack_pen'], m['roll_pen'], m['alt_cost'], m['hand_strain'],
            m['chord_strain'],
            alpha=alpha, theta=theta, eta=eta, omega=omega,
            lam_L=lam_L, lam_S=lam_S,
            cap_start=60.0, cap_range=30.0,
            duration=data['duration'],
            total_notes=data['total_notes'],
            uncap_level=True
        )
        est_level = calc.pattern_level_from_D0(
            res['D0'], D_min=0.0, D_max=D_max, gamma=gamma, uncap=True
        )
        total_error += abs(est_level - data['label'])
        
    return total_error / len(chart_data)

def objective_stage_2(params, chart_data, fixed_weights):
    """Stage 2: Physics Optimization"""
    lam_L, lam_S, gamma = params
    alpha, theta, eta, omega, D_max = fixed_weights
    
    total_error = 0.0
    for data in chart_data:
        m = data['metrics']
        res = calc.compute_map_difficulty(
            m['nps'], m['ln_strain'], m['jack_pen'], m['roll_pen'], m['alt_cost'], m['hand_strain'],
            m['chord_strain'],
            alpha=alpha, theta=theta, eta=eta, omega=omega,
            lam_L=lam_L, lam_S=lam_S,
            cap_start=60.0, cap_range=30.0,
            duration=data['duration'],
            total_notes=data['total_notes'],
            uncap_level=True
        )
        est_level = calc.pattern_level_from_D0(
            res['D0'], D_min=0.0, D_max=D_max, gamma=gamma, uncap=True
        )
        total_error += abs(est_level - data['label'])
        
    return total_error / len(chart_data)

def run_optimization_for_tier(tier_name, tier_data):
    print(f"\n>>> Optimizing Tier: {tier_name} ({len(tier_data)} charts)")
    
    if len(tier_data) < 5:
        print("Not enough data for this tier. Skipping.")
        return None

    best_mae = float('inf')
    best_params = None
    
    # Simple 3-Fold
    kf = KFold(n_splits=3, shuffle=True, random_state=42)
    
    fold_idx = 0
    for train_index, test_index in kf.split(tier_data):
        fold_idx += 1
        train_data = [tier_data[i] for i in train_index]
        test_data = [tier_data[i] for i in test_index]
        
        # Stage 1
        fixed_physics = [0.3, 0.8, 1.0] 
        init_weights = [1.0, 1.0, 0.5, 1.0, 100.0]
        bounds_weights = [(0.1, 5.0), (0.1, 5.0), (0.0, 3.0), (0.5, 2.0), (50.0, 150.0)]
        
        res1 = minimize(
            objective_stage_1, init_weights, args=(train_data, fixed_physics),
            method='L-BFGS-B', bounds=bounds_weights
        )
        best_weights_iter = res1.x

        # Stage 2
        init_physics = [0.3, 0.8, 1.0]
        bounds_physics = [(0.05, 0.5), (0.5, 0.95), (0.8, 1.5)]
        
        res2 = minimize(
            objective_stage_2, init_physics, args=(train_data, best_weights_iter),
            method='L-BFGS-B', bounds=bounds_physics
        )
        best_physics_iter = res2.x
        
        # Validation
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
                    D_max=D_max, gamma_curve=gamma
                )
                est_level = res['est_level']
                total_error += abs(est_level - data['label'])
            return total_error / len(dataset)

        test_mae = calculate_mae(test_data)
        print(f"  Fold {fold_idx}: Test MAE={test_mae:.4f}")
        
        if test_mae < best_mae:
            best_mae = test_mae
            best_params = {
                'weights': best_weights_iter.tolist(),
                'physics': best_physics_iter.tolist(),
                'mae': test_mae
            }
            
    return best_params

def optimize_segmented():
    all_data = load_charts()
    if not all_data: return

    segmented_results = {}
    
    for min_lv, max_lv, name in TIERS:
        # Filter data for this tier
        tier_data = [d for d in all_data if min_lv <= d['label'] < max_lv]
        
        if not tier_data:
            print(f"No data for {name} ({min_lv}-{max_lv})")
            continue
            
        result = run_optimization_for_tier(f"{name} ({min_lv}-{max_lv})", tier_data)
        
        if result:
            segmented_results[name] = {
                'range': [min_lv, max_lv],
                'count': len(tier_data),
                'params': result
            }
            
            # Print Summary
            p = result
            w = p['weights']
            ph = p['physics']
            print(f"  [Result] MAE: {p['mae']:.4f}")
            print(f"  Weights: A={w[0]:.2f}, Th={w[1]:.2f}, Et={w[2]:.2f}, Om={w[3]:.2f}, Dm={w[4]:.1f}")
            print(f"  Physics: lL={ph[0]:.2f}, lS={ph[1]:.2f}, Gm={ph[2]:.2f}")

    # Save
    with open(r"d:\계산기\segmented_params.json", "w", encoding='utf-8') as f:
        json.dump(segmented_results, f, indent=4)
    print("\nSaved segmented parameters to d:\\계산기\\segmented_params.json")

if __name__ == "__main__":
    optimize_segmented()
