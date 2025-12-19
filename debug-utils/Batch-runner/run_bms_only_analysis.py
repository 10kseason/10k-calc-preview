"""
BMS 전용 난이도 분석 스크립트
- Osu! 파일 제외
- NPS-only 베이스라인 vs 현재 모델 비교
"""

import os
import json
import time
import numpy as np
from scipy import stats
import bms_parser
import calc
import metric_calc
import gc

def scan_bms_files(target_dirs):
    """BMS 파일만 스캔 (.bms, .bme, .bml)"""
    extensions = {'.bms', '.bme', '.bml'}
    for root_dir in target_dirs:
        for root, dirs, files in os.walk(root_dir):
            for file in files:
                if os.path.splitext(file)[1].lower() in extensions:
                    yield os.path.join(root, file)

def get_bms_metadata(file_path, parser_header):
    """BMS 메타데이터 추출"""
    label = None
    title = parser_header.get('TITLE', 'Unknown')
    
    if 'PLAYLEVEL' in parser_header:
        try:
            label = int(parser_header['PLAYLEVEL'])
        except: pass
        
    if label is None:
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    if line.upper().startswith("#PLAYLEVEL"):
                        try:
                            label = int(line.split()[1])
                        except: pass
                    if line.upper().startswith("#TITLE") and title == 'Unknown':
                        try:
                            title = line.split(maxsplit=1)[1].strip()
                        except: pass
                    if label is not None and title != 'Unknown':
                        break
        except: pass
        
    return title, label

def run_analysis():
    # 1. Setup Paths (BMS만 포함된 디렉토리)
    target_dirs = [
        r"d:\계산기\테스트 샘플",
        r"d:\계산기\패턴 모음",
        r"d:\계산기\패턴 모음2(GCS)",
    ]
    
    # 2. Load Final Params
    final_params = {}
    try:
        with open(r"d:\계산기\final_params.json", "r", encoding='utf-8') as f:
            final_params = json.load(f)
        print("Loaded final params from final_params.json")
    except Exception as e:
        print(f"Could not load final_params.json: {e}")
        return

    # 3. Processing Loop
    print("Starting BMS-Only Analysis...")
    start_time = time.time()
    
    results = []
    count = 0
    
    for file_path in scan_bms_files(target_dirs):
        try:
            is_gcs = "패턴 모음2(GCS)" in file_path
            
            parser = bms_parser.BMSParser(file_path)
            notes = parser.parse()
            
            duration = parser.duration
            header_copy = parser.header.copy() if hasattr(parser, 'header') else {}
            
            del parser 
            
            if not notes: continue
            if duration < 10: continue
            
            # Get Label & Title
            title, label = get_bms_metadata(file_path, header_copy)
            
            # GCS Filtering Rules
            if is_gcs:
                if label is None or label == 0: continue 
                label = label - 5
                if label < 1: continue
                        
            if label is None:
                continue
            
            # Calculate Metrics
            metrics = metric_calc.calculate_metrics(notes, duration)
            total_notes = len(notes)
            del notes
            
            # NPS Baseline (total notes / duration)
            nps_baseline = total_notes / duration
            
            # Current Model
            p = final_params
            res = calc.compute_map_difficulty(
                metrics['nps'], metrics['ln_strain'], metrics['jack_pen'], 
                metrics['roll_pen'], metrics['alt_cost'], metrics['hand_strain'],
                metrics['chord_strain'],
                alpha=p.get('alpha', 0.8), 
                beta=p.get('beta', 1.0), 
                gamma=p.get('gamma', 1.0), 
                delta=p.get('delta', 1.0), 
                eta=p.get('eta', 0.5), 
                theta=p.get('theta', 0.5),
                omega=p.get('omega', 1.5),
                lam_L=p.get('lam_L', 0.3), 
                lam_S=p.get('lam_S', 0.8),
                D_min=p.get('D_min', 0.0),
                D_max=p.get('D_max', 75.0), 
                gamma_curve=p.get('gamma_curve', 1.0),
                duration=duration,
                total_notes=total_notes, 
                uncap_level=True
            )
            
            results.append({
                'file': os.path.basename(file_path),
                'title': title,
                'label': label,
                'nps_baseline': nps_baseline,
                'model_level': res['pattern_level'],
                'D0': res['D0'],
                'is_gcs': is_gcs
            })
            
            count += 1
            if count % 100 == 0:
                print(f"Processed {count} files...", flush=True)
                gc.collect()
                
        except Exception as e:
            pass

    end_time = time.time()
    total_time = end_time - start_time
    
    print(f"\nTotal Charts: {len(results)} (in {total_time:.2f}s)")
    
    if not results:
        print("No valid BMS charts found!")
        return
    
    # 4. NPS Baseline Linear Regression
    # level = slope * NPS + intercept
    nps_values = np.array([r['nps_baseline'] for r in results])
    labels = np.array([r['label'] for r in results])
    
    slope, intercept, r_value, p_value, std_err = stats.linregress(nps_values, labels)
    
    print(f"\n=== NPS Baseline Linear Regression ===")
    print(f"Formula: level = {slope:.4f} * NPS + {intercept:.4f}")
    print(f"R-squared: {r_value**2:.4f}")
    
    # Compute NPS-only predicted levels
    for r in results:
        r['nps_pred_level'] = slope * r['nps_baseline'] + intercept
    
    # 5. Calculate MAE for both models
    nps_errors = [abs(r['nps_pred_level'] - r['label']) for r in results]
    model_errors = [abs(r['model_level'] - r['label']) for r in results]
    
    nps_mae = np.mean(nps_errors)
    model_mae = np.mean(model_errors)
    
    print(f"\n=== MAE Comparison ===")
    print(f"NPS-only Baseline MAE: {nps_mae:.4f}")
    print(f"Current Model MAE:     {model_mae:.4f}")
    print(f"Improvement:           {nps_mae - model_mae:.4f} ({(nps_mae - model_mae) / nps_mae * 100:.1f}%)")
    
    # 6. Breakdown by source
    gcs_results = [r for r in results if r['is_gcs']]
    other_results = [r for r in results if not r['is_gcs']]
    
    if gcs_results:
        gcs_nps_mae = np.mean([abs(r['nps_pred_level'] - r['label']) for r in gcs_results])
        gcs_model_mae = np.mean([abs(r['model_level'] - r['label']) for r in gcs_results])
        print(f"\n[GCS Charts: {len(gcs_results)}]")
        print(f"  NPS Baseline MAE: {gcs_nps_mae:.4f}")
        print(f"  Model MAE:        {gcs_model_mae:.4f}")
    
    if other_results:
        other_nps_mae = np.mean([abs(r['nps_pred_level'] - r['label']) for r in other_results])
        other_model_mae = np.mean([abs(r['model_level'] - r['label']) for r in other_results])
        print(f"\n[Other BMS Charts: {len(other_results)}]")
        print(f"  NPS Baseline MAE: {other_nps_mae:.4f}")
        print(f"  Model MAE:        {other_model_mae:.4f}")
    
    # 7. Level Distribution
    print(f"\n=== Label Distribution ===")
    label_counts = {}
    for r in results:
        lbl = r['label']
        label_counts[lbl] = label_counts.get(lbl, 0) + 1
    
    for lbl in sorted(label_counts.keys()):
        bar = "#" * min(label_counts[lbl], 50)
        print(f"Lv.{lbl:2d}: {label_counts[lbl]:4d} | {bar}")
    
    # 8. Save detailed report
    report_path = r"d:\계산기\bms_only_report.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("=== BMS-Only Analysis Report ===\n")
        f.write(f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Total Charts: {len(results)}\n")
        f.write(f"Execution Time: {total_time:.2f}s\n\n")
        
        f.write("=== NPS Baseline Regression ===\n")
        f.write(f"Formula: level = {slope:.4f} * NPS + {intercept:.4f}\n")
        f.write(f"R-squared: {r_value**2:.4f}\n\n")
        
        f.write("=== MAE Comparison ===\n")
        f.write(f"NPS-only Baseline MAE: {nps_mae:.4f}\n")
        f.write(f"Current Model MAE:     {model_mae:.4f}\n")
        f.write(f"Improvement: {nps_mae - model_mae:.4f}\n\n")
        
        f.write("=== All Charts ===\n")
        f.write("Label | NPS_Pred | Model | Error_NPS | Error_Model | Title\n")
        for r in sorted(results, key=lambda x: x['label']):
            nps_err = abs(r['nps_pred_level'] - r['label'])
            model_err = abs(r['model_level'] - r['label'])
            f.write(f"{r['label']:5d} | {r['nps_pred_level']:8.2f} | {r['model_level']:5.2f} | {nps_err:9.2f} | {model_err:11.2f} | {r['title']}\n")
    
    print(f"\nReport saved to: {report_path}")
    
    # Return summary for further analysis
    return {
        'nps_mae': nps_mae,
        'model_mae': model_mae,
        'nps_formula': {'slope': slope, 'intercept': intercept},
        'total_charts': len(results),
        'results': results
    }

if __name__ == "__main__":
    run_analysis()
