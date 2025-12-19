"""
최적화된 선형 모델로 BMS 전체 분석
공식: level = -1.86 + 0.44*NPS + 1.47*nps_std + 0.66*chord_mean
"""

import os
import glob
import time
import numpy as np
from sklearn.linear_model import LinearRegression
import bms_parser
import metric_calc
import json

def load_and_analyze_all_bms():
    """BMS 전체 로드 및 분석"""
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
    
    # 피처 및 레이블 수집 (레이블 있는 것만)
    labeled_data = []
    all_data = []
    
    start_time = time.time()
    
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
            
            title = parser.header.get('TITLE', 'Unknown')
            
            # Get Label
            label = None
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
            original_label = label
            if is_gcs:
                if label is None or label == 0: continue
                label = label - 5
                if label < 1: continue
            
            # 이상치 제외 (Label >= 90)
            if label is not None and label >= 90:
                continue
            
            metrics = metric_calc.calculate_metrics(notes, duration)
            total_notes = len(notes)
            
            # 피처 계산
            global_nps = total_notes / duration
            nps_std = np.std(metrics['nps'])
            chord_mean = np.mean(metrics['chord_strain'])
            
            entry = {
                'file': os.path.basename(file_path),
                'title': title,
                'label': label,
                'global_nps': global_nps,
                'nps_std': nps_std,
                'chord_mean': chord_mean,
                'total_notes': total_notes,
                'duration': duration,
                'is_gcs': is_gcs
            }
            
            all_data.append(entry)
            
            if label is not None:
                labeled_data.append(entry)
                
        except Exception as e:
            pass
    
    end_time = time.time()
    print(f"\nLoaded {len(labeled_data)} labeled charts (out of {len(all_data)} total) in {end_time - start_time:.2f}s")
    
    return labeled_data, all_data

def run_full_analysis():
    labeled_data, all_data = load_and_analyze_all_bms()
    
    if not labeled_data:
        print("No labeled charts found!")
        return
    
    # 1. 모델 학습 (레이블 있는 데이터로)
    X = np.array([[d['global_nps'], d['nps_std'], d['chord_mean']] for d in labeled_data])
    y = np.array([d['label'] for d in labeled_data])
    
    model = LinearRegression()
    model.fit(X, y)
    
    print("\n" + "=" * 60)
    print("TRAINED LINEAR MODEL")
    print("=" * 60)
    print(f"Formula: level = {model.intercept_:.4f} + {model.coef_[0]:.4f}*NPS + {model.coef_[1]:.4f}*nps_std + {model.coef_[2]:.4f}*chord_mean")
    
    # 2. 예측 및 평가
    predictions = model.predict(X)
    
    for i, d in enumerate(labeled_data):
        d['predicted'] = predictions[i]
        d['error'] = abs(predictions[i] - d['label'])
    
    # 전체 통계
    errors = [d['error'] for d in labeled_data]
    mae = np.mean(errors)
    rmse = np.sqrt(np.mean([e**2 for e in errors]))
    
    residuals = [d['predicted'] - d['label'] for d in labeled_data]
    bias = np.mean(residuals)
    
    print(f"\n=== Overall Statistics ===")
    print(f"Total Charts: {len(labeled_data)}")
    print(f"MAE:  {mae:.4f}")
    print(f"RMSE: {rmse:.4f}")
    print(f"Bias: {bias:.4f}")
    
    # GCS vs Other 분석
    gcs_data = [d for d in labeled_data if d['is_gcs']]
    other_data = [d for d in labeled_data if not d['is_gcs']]
    
    if gcs_data:
        gcs_mae = np.mean([d['error'] for d in gcs_data])
        gcs_bias = np.mean([d['predicted'] - d['label'] for d in gcs_data])
        print(f"\n[GCS Charts: {len(gcs_data)}]")
        print(f"  MAE:  {gcs_mae:.4f}")
        print(f"  Bias: {gcs_bias:.4f}")
    
    if other_data:
        other_mae = np.mean([d['error'] for d in other_data])
        other_bias = np.mean([d['predicted'] - d['label'] for d in other_data])
        print(f"\n[Other BMS Charts: {len(other_data)}]")
        print(f"  MAE:  {other_mae:.4f}")
        print(f"  Bias: {other_bias:.4f}")
    
    # 레벨별 분석
    print(f"\n=== Per-Level Analysis ===")
    print(f"{'Level':<8} {'Count':>6} {'MAE':>8} {'Bias':>8}")
    print("-" * 35)
    
    level_groups = {}
    for d in labeled_data:
        lv = d['label']
        if lv not in level_groups:
            level_groups[lv] = []
        level_groups[lv].append(d)
    
    for lv in sorted(level_groups.keys()):
        group = level_groups[lv]
        lv_mae = np.mean([d['error'] for d in group])
        lv_bias = np.mean([d['predicted'] - d['label'] for d in group])
        print(f"Lv.{lv:<5} {len(group):>6} {lv_mae:>8.2f} {lv_bias:>+8.2f}")
    
    # Top 20 오차 큰 차트
    print(f"\n=== Top 20 Largest Errors ===")
    sorted_by_error = sorted(labeled_data, key=lambda x: x['error'], reverse=True)[:20]
    print(f"{'Error':>6} {'Label':>6} {'Pred':>6} {'Title'}")
    for d in sorted_by_error:
        print(f"{d['error']:>6.2f} {d['label']:>6} {d['predicted']:>6.1f} {d['title'][:50]}")
    
    # 리포트 저장
    report_path = r"d:\계산기\bms_linear_model_report.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("=== BMS Linear Model Analysis Report ===\n")
        f.write(f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Total Charts: {len(labeled_data)}\n\n")
        
        f.write("=== Model ===\n")
        f.write(f"level = {model.intercept_:.4f} + {model.coef_[0]:.4f}*NPS + {model.coef_[1]:.4f}*nps_std + {model.coef_[2]:.4f}*chord_mean\n\n")
        
        f.write("=== Statistics ===\n")
        f.write(f"MAE:  {mae:.4f}\n")
        f.write(f"RMSE: {rmse:.4f}\n")
        f.write(f"Bias: {bias:.4f}\n\n")
        
        f.write("=== All Charts ===\n")
        f.write(f"{'Label':>6} | {'Pred':>6} | {'Error':>6} | Title\n")
        for d in sorted(labeled_data, key=lambda x: x['label']):
            f.write(f"{d['label']:>6} | {d['predicted']:>6.1f} | {d['error']:>6.2f} | {d['title']}\n")
    
    print(f"\nReport saved to: {report_path}")
    
    # JSON 저장
    json_path = r"d:\계산기\bms_linear_model_params.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            'intercept': model.intercept_,
            'coef_global_nps': model.coef_[0],
            'coef_nps_std': model.coef_[1],
            'coef_chord_mean': model.coef_[2],
            'mae': mae,
            'rmse': rmse,
            'bias': bias,
            'total_charts': len(labeled_data)
        }, f, indent=2)
    
    print(f"Parameters saved to: {json_path}")

if __name__ == "__main__":
    run_full_analysis()
