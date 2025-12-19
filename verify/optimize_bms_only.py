"""
BMS 전용 파라미터 최적화 스크립트
Osu! 제외, BMS 데이터만 사용
"""

import os
import glob
import json
import numpy as np
import random
from scipy.optimize import minimize
from sklearn.model_selection import KFold
import bms_parser
import calc
import metric_calc

def load_bms_charts():
    """BMS 차트 데이터 로드 (레이블 있는 것만)"""
    target_dirs = [
        r"d:\계산기\테스트 샘플",
        r"d:\계산기\패턴 모음",
        r"d:\계산기\패턴 모음2(GCS)",
    ]
    
    files = []
    for root_dir in target_dirs:
        for ext in ['*.bms', '*.bme', '*.bml']:
            files.extend(glob.glob(os.path.join(root_dir, '**', ext), recursive=True))
            
    print(f"Found {len(files)} BMS files.")
    
    chart_data = []
    
    for i, file_path in enumerate(files):
        if i % 200 == 0:
            print(f"Processing {i}/{len(files)}...")
            
        try:
            is_gcs = "패턴 모음2(GCS)" in file_path
            
            parser = bms_parser.BMSParser(file_path)
            notes = parser.parse()
            if not notes: continue
                
            duration = parser.duration
            if duration < 10: continue
                
            # Get Label
            label = None
            title = "Unknown"
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
            
            # GCS Filtering
            if is_gcs:
                if label is None or label == 0: continue
                label = label - 5
                if label < 1: continue
            
            if label is None: continue
            
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
            
    print(f"Loaded {len(chart_data)} valid charts.")
    return chart_data

def objective_full(params, chart_data):
    """
    전체 파라미터 최적화 목적 함수
    params: [alpha, theta, eta, omega, lam_L, lam_S, D_min, D_max, gamma]
    """
    alpha, theta, eta, omega, lam_L, lam_S, D_min, D_max, gamma = params
    
    total_error = 0.0
    for data in chart_data:
        m = data['metrics']
        res = calc.compute_map_difficulty(
            m['nps'], m['ln_strain'], m['jack_pen'], 
            m['roll_pen'], m['alt_cost'], m['hand_strain'],
            m['chord_strain'],
            alpha=alpha, theta=theta, eta=eta, omega=omega,
            lam_L=lam_L, lam_S=lam_S,
            cap_start=60.0, cap_range=30.0,
            duration=data['duration'],
            total_notes=data['total_notes'],
            uncap_level=True,
            D_min=D_min, D_max=D_max, gamma_curve=gamma
        )
        total_error += abs(res['pattern_level'] - data['label'])
        
    return total_error / len(chart_data)

def optimize_bms_only():
    # 1. Load Data
    print("Loading BMS charts...")
    all_data = load_bms_charts()
    
    if not all_data: 
        print("No charts found.")
        return

    print(f"\n총 {len(all_data)}개 BMS 차트 로드됨\n")
    
    best_mae = float('inf')
    best_params = None
    
    # 5-Fold Cross Validation
    kf = KFold(n_splits=5, shuffle=True, random_state=42)
    
    print("Starting 5-Fold Cross-Validation Optimization...")
    print("-" * 60)
    
    # 초기값 및 경계
    # [alpha, theta, eta, omega, lam_L, lam_S, D_min, D_max, gamma]
    init_params = [1.0, 1.0, 0.5, 1.0, 0.3, 0.8, 0.0, 50.0, 0.5]
    bounds = [
        (0.1, 5.0),   # alpha
        (0.1, 5.0),   # theta
        (0.0, 3.0),   # eta
        (0.1, 3.0),   # omega
        (0.05, 0.5),  # lam_L
        (0.5, 0.95),  # lam_S
        (0.0, 20.0),  # D_min
        (20.0, 150.0),# D_max
        (0.2, 2.0),   # gamma
    ]
    
    fold_results = []
    
    fold_idx = 0
    for train_index, test_index in kf.split(all_data):
        fold_idx += 1
        
        train_data = [all_data[i] for i in train_index]
        test_data = [all_data[i] for i in test_index]
        
        print(f"\nFold {fold_idx}: Train={len(train_data)}, Test={len(test_data)}")
        
        # Optimize
        result = minimize(
            objective_full, init_params, args=(train_data,),
            method='L-BFGS-B', bounds=bounds,
            options={'maxiter': 200}
        )
        
        opt_params = result.x
        train_mae = result.fun
        
        # Test MAE
        test_mae = objective_full(opt_params, test_data)
        
        print(f"  Train MAE: {train_mae:.4f}")
        print(f"  Test MAE:  {test_mae:.4f}")
        
        fold_results.append({
            'fold': fold_idx,
            'train_mae': train_mae,
            'test_mae': test_mae,
            'params': opt_params.tolist()
        })
        
        if test_mae < best_mae:
            best_mae = test_mae
            best_params = opt_params
    
    print("\n" + "=" * 60)
    print("BEST RESULT")
    print("=" * 60)
    print(f"Best Test MAE: {best_mae:.4f}")
    
    alpha, theta, eta, omega, lam_L, lam_S, D_min, D_max, gamma = best_params
    
    print(f"\nOptimized Parameters:")
    print(f"  alpha (NPS):    {alpha:.4f}")
    print(f"  theta (Hand):   {theta:.4f}")
    print(f"  eta (Alt):      {eta:.4f}")
    print(f"  omega (Chord):  {omega:.4f}")
    print(f"  lam_L:          {lam_L:.4f}")
    print(f"  lam_S:          {lam_S:.4f}")
    print(f"  D_min:          {D_min:.4f}")
    print(f"  D_max:          {D_max:.4f}")
    print(f"  gamma:          {gamma:.4f}")
    
    # Final validation on all data
    final_mae = objective_full(best_params, all_data)
    print(f"\nFinal MAE (All Data): {final_mae:.4f}")
    
    # Save to JSON
    output = {
        'alpha': float(alpha),
        'theta': float(theta),
        'eta': float(eta),
        'omega': float(omega),
        'lam_L': float(lam_L),
        'lam_S': float(lam_S),
        'D_min': float(D_min),
        'D_max': float(D_max),
        'gamma_curve': float(gamma),
        'mae': float(final_mae),
        'best_test_mae': float(best_mae),
        'total_charts': len(all_data)
    }
    
    output_path = r"d:\계산기\bms_final_params.json"
    with open(output_path, "w", encoding='utf-8') as f:
        json.dump(output, f, indent=4)
    
    print(f"\nSaved to: {output_path}")
    
    return output

if __name__ == "__main__":
    optimize_bms_only()
