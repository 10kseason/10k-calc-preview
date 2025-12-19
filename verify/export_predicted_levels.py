"""
전체 BMS 파일 예측 레벨 CSV 출력
학습된 모델로 모든 파일의 레벨 예측
"""

import os
import glob
import numpy as np
import bms_parser
import metric_calc
import csv

# 학습된 모델 계수 (bms_linear_model_params.json에서)
INTERCEPT = -0.1879
COEF_NPS = 0.2053
COEF_NPS_STD = 0.9999
COEF_CHORD_MEAN = 3.2741

def predict_level(global_nps, nps_std, chord_mean):
    """선형 모델로 레벨 예측"""
    return INTERCEPT + COEF_NPS * global_nps + COEF_NPS_STD * nps_std + COEF_CHORD_MEAN * chord_mean

def generate_csv():
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
    
    results = []
    
    for i, file_path in enumerate(files):
        if i % 300 == 0:
            print(f"Processing {i}/{len(files)}...")
            
        try:
            parser = bms_parser.BMSParser(file_path)
            notes = parser.parse()
            if not notes: continue
                
            duration = parser.duration
            if duration < 10: continue
            
            title = parser.header.get('TITLE', 'Unknown')
            
            # Get original label (if exists)
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
            
            metrics = metric_calc.calculate_metrics(notes, duration)
            total_notes = len(notes)
            
            # 피처 계산
            global_nps = total_notes / duration
            nps_std = np.std(metrics['nps'])
            chord_mean = np.mean(metrics['chord_strain'])
            
            # 예측 레벨
            predicted = predict_level(global_nps, nps_std, chord_mean)
            
            # GCS 여부
            is_gcs = "패턴 모음2(GCS)" in file_path
            
            results.append({
                'file_path': file_path,
                'file_name': os.path.basename(file_path),
                'title': title,
                'original_label': label if label else '',
                'predicted_level': round(predicted, 2),
                'global_nps': round(global_nps, 2),
                'nps_std': round(nps_std, 2),
                'chord_mean': round(chord_mean, 4),
                'total_notes': total_notes,
                'duration_sec': round(duration, 1),
                'is_gcs': is_gcs
            })
                
        except Exception as e:
            pass
    
    # CSV 저장
    csv_path = r"d:\계산기\bms_predicted_levels.csv"
    
    with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
        fieldnames = ['title', 'predicted_level', 'original_label', 'global_nps', 'nps_std', 
                      'chord_mean', 'total_notes', 'duration_sec', 'is_gcs', 'file_name', 'file_path']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        # 예측 레벨 기준 정렬
        for r in sorted(results, key=lambda x: x['predicted_level'], reverse=True):
            writer.writerow(r)
    
    print(f"\nTotal: {len(results)} files")
    print(f"CSV saved to: {csv_path}")
    
    # 간단한 통계
    preds = [r['predicted_level'] for r in results]
    print(f"\nPredicted Level Stats:")
    print(f"  Min: {min(preds):.1f}")
    print(f"  Max: {max(preds):.1f}")
    print(f"  Mean: {np.mean(preds):.1f}")
    print(f"  Median: {np.median(preds):.1f}")

if __name__ == "__main__":
    generate_csv()
