"""
NPS + 추가 피처 다중 선형 회귀 탐색
- NPS 선형 회귀(MAE 1.55)를 기반으로 추가 피처 조합 탐색
- 어떤 피처를 더해야 정확도가 개선되는지 분석
"""

import os
import glob
import numpy as np
from sklearn.linear_model import LinearRegression, Ridge, Lasso
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import cross_val_score, KFold
import bms_parser
import metric_calc
import json

def load_bms_charts():
    """BMS 차트 데이터 로드"""
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
        if i % 300 == 0:
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
            
            # 피처 추출
            global_nps = total_notes / duration
            
            # 윈도우 기반 메트릭 집계 (평균, 최대, 표준편차)
            chart_data.append({
                'label': label,
                'global_nps': global_nps,
                'duration': duration,
                'total_notes': total_notes,
                # 평균값
                'nps_mean': np.mean(metrics['nps']),
                'nps_max': np.max(metrics['nps']),
                'nps_std': np.std(metrics['nps']),
                'jack_mean': np.mean(metrics['jack_pen']),
                'jack_max': np.max(metrics['jack_pen']),
                'ln_mean': np.mean(metrics['ln_strain']),
                'ln_max': np.max(metrics['ln_strain']),
                'roll_mean': np.mean(metrics['roll_pen']),
                'roll_max': np.max(metrics['roll_pen']),
                'alt_mean': np.mean(metrics['alt_cost']),
                'alt_max': np.max(metrics['alt_cost']),
                'hand_mean': np.mean(metrics['hand_strain']),
                'hand_max': np.max(metrics['hand_strain']),
                'chord_mean': np.mean(metrics['chord_strain']),
                'chord_max': np.max(metrics['chord_strain']),
            })
                
        except Exception as e:
            pass
            
    print(f"Loaded {len(chart_data)} valid charts.")
    return chart_data

def run_linear_regression_analysis():
    print("Loading BMS charts...")
    chart_data = load_bms_charts()
    
    if not chart_data:
        print("No charts found!")
        return
    
    labels = np.array([d['label'] for d in chart_data])
    
    # 피처 목록 정의
    feature_sets = {
        # 단일 피처
        'global_nps': ['global_nps'],
        
        # NPS + 하나씩
        'global_nps + nps_max': ['global_nps', 'nps_max'],
        'global_nps + nps_std': ['global_nps', 'nps_std'],
        'global_nps + jack_mean': ['global_nps', 'jack_mean'],
        'global_nps + jack_max': ['global_nps', 'jack_max'],
        'global_nps + ln_mean': ['global_nps', 'ln_mean'],
        'global_nps + hand_mean': ['global_nps', 'hand_mean'],
        'global_nps + chord_mean': ['global_nps', 'chord_mean'],
        'global_nps + chord_max': ['global_nps', 'chord_max'],
        'global_nps + alt_mean': ['global_nps', 'alt_mean'],
        
        # NPS + 2개
        'global_nps + jack_max + chord_mean': ['global_nps', 'jack_max', 'chord_mean'],
        'global_nps + nps_std + chord_mean': ['global_nps', 'nps_std', 'chord_mean'],
        'global_nps + nps_max + jack_max': ['global_nps', 'nps_max', 'jack_max'],
        'global_nps + hand_mean + chord_mean': ['global_nps', 'hand_mean', 'chord_mean'],
        
        # NPS + 3개
        'global_nps + jack_max + chord_mean + hand_mean': ['global_nps', 'jack_max', 'chord_mean', 'hand_mean'],
        'global_nps + nps_std + jack_max + chord_mean': ['global_nps', 'nps_std', 'jack_max', 'chord_mean'],
        
        # 전체
        'all_features': ['global_nps', 'nps_max', 'nps_std', 'jack_mean', 'jack_max', 
                        'ln_mean', 'ln_max', 'roll_mean', 'hand_mean', 'hand_max', 
                        'chord_mean', 'chord_max', 'alt_mean'],
    }
    
    results = []
    
    print("\n=== Linear Regression Feature Analysis ===\n")
    print(f"{'Features':<50} {'MAE':>8} {'RMSE':>8} {'R²':>8}")
    print("-" * 80)
    
    kf = KFold(n_splits=5, shuffle=True, random_state=42)
    
    for name, features in feature_sets.items():
        # 피처 행렬 생성
        X = np.array([[d[f] for f in features] for d in chart_data])
        
        # 스케일링
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        
        # Cross-validation
        model = LinearRegression()
        
        # MAE
        mae_scores = cross_val_score(model, X_scaled, labels, cv=kf, scoring='neg_mean_absolute_error')
        mae = -mae_scores.mean()
        
        # RMSE
        rmse_scores = cross_val_score(model, X_scaled, labels, cv=kf, scoring='neg_root_mean_squared_error')
        rmse = -rmse_scores.mean()
        
        # R²
        r2_scores = cross_val_score(model, X_scaled, labels, cv=kf, scoring='r2')
        r2 = r2_scores.mean()
        
        results.append({
            'name': name,
            'features': features,
            'mae': mae,
            'rmse': rmse,
            'r2': r2
        })
        
        print(f"{name:<50} {mae:>8.4f} {rmse:>8.4f} {r2:>8.4f}")
    
    # 정렬
    results_sorted = sorted(results, key=lambda x: x['mae'])
    
    print("\n" + "=" * 80)
    print("TOP 5 Best Feature Combinations (by MAE)")
    print("=" * 80)
    
    for i, r in enumerate(results_sorted[:5], 1):
        print(f"\n{i}. {r['name']}")
        print(f"   MAE: {r['mae']:.4f}, RMSE: {r['rmse']:.4f}, R²: {r['r2']:.4f}")
        print(f"   Features: {r['features']}")
    
    # 최고 모델 계수 출력
    best = results_sorted[0]
    features = best['features']
    X = np.array([[d[f] for f in features] for d in chart_data])
    
    model = LinearRegression()
    model.fit(X, labels)
    
    print("\n" + "=" * 80)
    print(f"Best Model Coefficients: {best['name']}")
    print("=" * 80)
    print(f"Formula: level = {model.intercept_:.4f}", end="")
    for feat, coef in zip(features, model.coef_):
        sign = "+" if coef >= 0 else ""
        print(f" {sign}{coef:.4f}*{feat}", end="")
    print()
    
    # 결과 저장
    output_path = r"d:\계산기\linear_regression_analysis.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump({
            'results': results_sorted,
            'best_model': {
                'name': best['name'],
                'features': features,
                'intercept': model.intercept_,
                'coefficients': dict(zip(features, model.coef_.tolist())),
                'mae': best['mae'],
                'rmse': best['rmse'],
                'r2': best['r2']
            }
        }, f, indent=2)
    
    print(f"\nResults saved to: {output_path}")
    
    return results_sorted

if __name__ == "__main__":
    run_linear_regression_analysis()
