"""
Feature Ablation Study for BMS Difficulty Calculator
각 피처의 정확도 기여도를 분석합니다.
"""

import os
import glob
import json
import numpy as np
from scipy import stats
from scipy.optimize import minimize
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
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    if line.upper().startswith("#PLAYLEVEL"):
                        try:
                            label = int(line.split()[1])
                        except: pass
                        break
            
            # GCS Filtering
            if is_gcs:
                if label is None or label == 0: continue
                label = label - 5
                if label < 1: continue
            
            if label is None: continue
            
            metrics = metric_calc.calculate_metrics(notes, duration)
            total_notes = len(notes)
            
            # Compute global NPS (total notes / duration)
            global_nps = total_notes / duration
            
            chart_data.append({
                'metrics': metrics,
                'duration': duration,
                'total_notes': total_notes,
                'label': label,
                'global_nps': global_nps,
                'file': os.path.basename(file_path)
            })
                
        except Exception as e:
            pass
            
    print(f"Loaded {len(chart_data)} valid charts.")
    return chart_data

def compute_level_with_features(chart_data, features, D_max=None, gamma=None):
    """
    주어진 피처 조합으로 레벨 계산
    features: dict - 사용할 피처와 weight (예: {'nps': 1.0, 'jack': 0.5})
    """
    # 기본값
    weights = {
        'nps': features.get('nps', 0),       # alpha
        'ln': features.get('ln', 0),         # beta
        'jack': features.get('jack', 0),     # gamma (weight)
        'roll': features.get('roll', 0),     # delta
        'alt': features.get('alt', 0),       # eta
        'hand': features.get('hand', 0),     # theta
        'chord': features.get('chord', 0),   # omega
    }
    
    if D_max is None:
        D_max = 50.0
    if gamma is None:
        gamma = 0.5
    
    predictions = []
    
    for data in chart_data:
        m = data['metrics']
        
        res = calc.compute_map_difficulty(
            m['nps'], m['ln_strain'], m['jack_pen'], 
            m['roll_pen'], m['alt_cost'], m['hand_strain'],
            m['chord_strain'],
            alpha=weights['nps'], 
            beta=weights['ln'], 
            gamma=weights['jack'], 
            delta=weights['roll'], 
            eta=weights['alt'], 
            theta=weights['hand'],
            omega=weights['chord'],
            lam_L=0.3, lam_S=0.8,
            cap_start=60.0, cap_range=30.0,
            duration=data['duration'],
            total_notes=data['total_notes'],
            uncap_level=True,
            D_max=D_max,
            gamma_curve=gamma
        )
        
        predictions.append({
            'pred': res['pattern_level'],
            'label': data['label'],
            'D0': res['D0']
        })
    
    return predictions

def optimize_for_features(chart_data, feature_combo):
    """주어진 피처 조합에 대해 D_max, gamma 최적화"""
    
    def objective(params):
        D_max, gamma = params
        
        # 피처 weights 고정 (각각 1.0)
        features = {f: 1.0 for f in feature_combo}
        
        preds = compute_level_with_features(chart_data, features, D_max, gamma)
        mae = np.mean([abs(p['pred'] - p['label']) for p in preds])
        return mae
    
    # Optimize D_max and gamma
    result = minimize(objective, [50.0, 0.5], method='L-BFGS-B',
                     bounds=[(10.0, 200.0), (0.1, 2.0)])
    
    return result.x[0], result.x[1], result.fun

def run_ablation_study():
    print("Loading BMS charts...")
    chart_data = load_bms_charts()
    
    if not chart_data:
        print("No charts found!")
        return
    
    # 1. NPS-only Baseline (Linear Regression)
    print("\n=== NPS-only Baseline (Linear Regression) ===")
    nps_values = np.array([d['global_nps'] for d in chart_data])
    labels = np.array([d['label'] for d in chart_data])
    
    slope, intercept, r_value, _, _ = stats.linregress(nps_values, labels)
    nps_preds = slope * nps_values + intercept
    nps_mae = np.mean(np.abs(nps_preds - labels))
    
    print(f"Formula: level = {slope:.4f} * NPS + {intercept:.4f}")
    print(f"MAE: {nps_mae:.4f}")
    
    # 2. Feature Ablation Study
    print("\n=== Feature Ablation Study ===")
    
    # 피처 목록
    all_features = ['nps', 'jack', 'ln', 'roll', 'alt', 'hand', 'chord']
    
    results = []
    
    # (a) NPS Only (using model, not linear regression)
    print("\nTesting: NPS only...")
    D_max, gamma, mae = optimize_for_features(chart_data, ['nps'])
    results.append({
        'features': 'nps',
        'D_max': D_max,
        'gamma': gamma,
        'mae': mae
    })
    print(f"  MAE: {mae:.4f} (D_max={D_max:.1f}, gamma={gamma:.3f})")
    
    # (b) NPS + 각 피처 하나씩 추가
    for feature in ['jack', 'ln', 'roll', 'alt', 'hand', 'chord']:
        print(f"\nTesting: NPS + {feature}...")
        D_max, gamma, mae = optimize_for_features(chart_data, ['nps', feature])
        results.append({
            'features': f'nps+{feature}',
            'D_max': D_max,
            'gamma': gamma,
            'mae': mae
        })
        print(f"  MAE: {mae:.4f} (D_max={D_max:.1f}, gamma={gamma:.3f})")
    
    # (c) All features
    print("\nTesting: All features...")
    D_max, gamma, mae = optimize_for_features(chart_data, all_features)
    results.append({
        'features': 'all',
        'D_max': D_max,
        'gamma': gamma,
        'mae': mae
    })
    print(f"  MAE: {mae:.4f} (D_max={D_max:.1f}, gamma={gamma:.3f})")
    
    # 3. Summary Table
    print("\n" + "=" * 60)
    print("ABLATION STUDY SUMMARY")
    print("=" * 60)
    print(f"{'Features':<20} {'MAE':>8} {'D_max':>8} {'Gamma':>8}")
    print("-" * 60)
    print(f"{'NPS Linear Reg':<20} {nps_mae:>8.4f} {'N/A':>8} {'N/A':>8}")
    
    for r in results:
        print(f"{r['features']:<20} {r['mae']:>8.4f} {r['D_max']:>8.1f} {r['gamma']:>8.3f}")
    
    print("=" * 60)
    
    # 4. Save results
    output_path = r"d:\계산기\ablation_results.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump({
            'nps_linear': {
                'slope': slope,
                'intercept': intercept,
                'mae': nps_mae
            },
            'ablation': results
        }, f, indent=2)
    
    print(f"\nResults saved to: {output_path}")
    
    return results

if __name__ == "__main__":
    run_ablation_study()
