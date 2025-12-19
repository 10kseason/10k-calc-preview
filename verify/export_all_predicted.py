"""
패턴 모음 + Osu 전체 파일 예측 레벨 CSV 출력
데이터셋으로 쓰지 않고 예측만
"""

import os
import glob
import numpy as np
import bms_parser
import osu_parser
import metric_calc
import csv

# 학습된 모델 계수
INTERCEPT = -0.1879
COEF_NPS = 0.2053
COEF_NPS_STD = 0.9999
COEF_CHORD_MEAN = 3.2741

def predict_level(global_nps, nps_std, chord_mean):
    return INTERCEPT + COEF_NPS * global_nps + COEF_NPS_STD * nps_std + COEF_CHORD_MEAN * chord_mean

def analyze_and_export(target_dir, output_csv, file_type='bms'):
    """특정 디렉토리 분석 후 CSV 출력"""
    
    if file_type == 'bms':
        extensions = ['*.bms', '*.bme', '*.bml']
    else:
        extensions = ['*.osu']
    
    files = []
    for ext in extensions:
        files.extend(glob.glob(os.path.join(target_dir, '**', ext), recursive=True))
            
    print(f"Found {len(files)} {file_type.upper()} files in {target_dir}")
    
    results = []
    
    for i, file_path in enumerate(files):
        if i % 500 == 0:
            print(f"Processing {i}/{len(files)}...")
            
        try:
            if file_type == 'osu':
                parser = osu_parser.OsuParser(file_path)
                notes = parser.parse()
                if not notes: continue
                
                # 10K만 분석
                if parser.key_count != 10:
                    continue
                    
                title = parser.header.get('Title', 'Unknown')
                label = None  # Osu는 레이블 없음
            else:
                parser = bms_parser.BMSParser(file_path)
                notes = parser.parse()
                if not notes: continue
                
                title = parser.header.get('TITLE', 'Unknown')
                
                # Get label
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
                
            duration = parser.duration
            if duration < 10: continue
            
            metrics = metric_calc.calculate_metrics(notes, duration)
            total_notes = len(notes)
            
            global_nps = total_notes / duration
            nps_std = np.std(metrics['nps'])
            chord_mean = np.mean(metrics['chord_strain'])
            
            predicted = predict_level(global_nps, nps_std, chord_mean)
            
            results.append({
                'title': title,
                'predicted_level': round(predicted, 2),
                'original_label': label if label else '',
                'global_nps': round(global_nps, 2),
                'nps_std': round(nps_std, 2),
                'chord_mean': round(chord_mean, 4),
                'total_notes': total_notes,
                'duration_sec': round(duration, 1),
                'file_name': os.path.basename(file_path),
                'file_path': file_path
            })
                
        except Exception as e:
            pass
    
    # CSV 저장
    with open(output_csv, 'w', newline='', encoding='utf-8-sig') as f:
        fieldnames = ['title', 'predicted_level', 'original_label', 'global_nps', 'nps_std', 
                      'chord_mean', 'total_notes', 'duration_sec', 'file_name', 'file_path']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for r in sorted(results, key=lambda x: x['predicted_level'], reverse=True):
            writer.writerow(r)
    
    print(f"Total: {len(results)} files")
    print(f"CSV saved to: {output_csv}")
    
    if results:
        preds = [r['predicted_level'] for r in results]
        print(f"  Level Range: {min(preds):.1f} ~ {max(preds):.1f}")
        print(f"  Mean: {np.mean(preds):.1f}, Median: {np.median(preds):.1f}")
    
    return results

if __name__ == "__main__":
    # 1. 패턴 모음 (BMS)
    print("\n" + "=" * 60)
    print("1. 패턴 모음 분석")
    print("=" * 60)
    analyze_and_export(
        r"d:\계산기\패턴 모음",
        r"d:\계산기\패턴모음_predicted.csv",
        'bms'
    )
    
    # 2. Osu 전체 (10K만)
    print("\n" + "=" * 60)
    print("2. Osu 폴더 전체 분석 (10K)")
    print("=" * 60)
    analyze_and_export(
        r"d:\계산기\osu 폴더 전체",
        r"d:\계산기\osu_predicted.csv",
        'osu'
    )
