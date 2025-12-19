import os
import glob
import bms_parser
import calc
import metric_calc
import numpy as np
import time

def verify_batch_levels(root_dirs):
    if isinstance(root_dirs, str):
        root_dirs = [root_dirs]
        
    files = []
    for root_dir in root_dirs:
        print(f"Scanning {root_dir} for BMS files...")
        for ext in ['*.bms', '*.bme', '*.bml']:
            files.extend(glob.glob(os.path.join(root_dir, '**', ext), recursive=True))
        
    print(f"Found {len(files)} files total.")
    
    results = []
    
    start_time = time.time()
    
    for i, file_path in enumerate(files):
        try:
            # 1. Parse Header for PLAYLEVEL
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                header_lines = f.readlines()
                
            play_level = None
            title = "Unknown"
            
            for line in header_lines:
                if line.upper().startswith("#PLAYLEVEL"):
                    try:
                        play_level = int(line.split()[1])
                    except:
                        pass
                if line.upper().startswith("#TITLE"):
                    title = line.split(maxsplit=1)[1].strip() if len(line.split()) > 1 else "Unknown"
                    
            if play_level is None:
                continue
                
            # Filter reasonable levels (e.g., 1-25)
            if not (1 <= play_level <= 25):
                continue
                
            # 2. Parse Chart and Calculate
            try:
                parser = bms_parser.BMSParser(file_path)
                notes = parser.parse()
            except Exception as e:
                continue
            
            if not notes:
                continue
                
            # Calculate Metrics
            duration = notes[-1]['time'] - notes[0]['time'] if notes else 0
            if duration < 10:
                continue
                
            metrics = metric_calc.calculate_metrics(notes, duration)
                
            res = calc.compute_map_difficulty(
                metrics['nps'], metrics['ln_strain'], metrics['jack_pen'], 
                metrics['roll_pen'], metrics['alt_cost'], metrics['hand_strain'],
                metrics['chord_strain'], # [NEW]
                duration=duration,
                total_notes=len(notes),
                uncap_level=False, # We want to compare with capped 1-25
                D_max=55.0,
                gamma_curve=1.0,
            )
            
            est_level = res['est_level']
            d0 = res['D0']
            
            results.append({
                'file': os.path.basename(file_path),
                'title': title,
                'labeled': play_level,
                'estimated': est_level,
                'd0': d0,
                'diff': est_level - play_level
            })
            
            if i % 100 == 0:
                print(f"Processed {i}/{len(files)}...")
                
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
            import traceback
            traceback.print_exc()
            pass

    end_time = time.time()
    print(f"\nProcessing complete in {end_time - start_time:.2f}s")
    print(f"Valid Samples: {len(results)}")
    
    if not results:
        return

    # Analysis
    diffs = [r['diff'] for r in results]
    mae = np.mean(np.abs(diffs))
    mse = np.mean(np.square(diffs))
    bias = np.mean(diffs)
    
    report_lines = []
    report_lines.append("\n=== Verification Report ===")
    report_lines.append(f"MAE (Mean Absolute Error): {mae:.2f}")
    report_lines.append(f"Bias (Mean Error): {bias:.2f} (Positive = Overestimated, Negative = Underestimated)")
    report_lines.append(f"Accuracy (Exact Match): {np.mean([d == 0 for d in diffs]):.2%}")
    report_lines.append(f"Accuracy (+-1 Level): {np.mean([abs(d) <= 1 for d in diffs]):.2%}")
    
    report_lines.append("\n=== Worst Outliers (Top 10 Overestimated) ===")
    sorted_res = sorted(results, key=lambda x: x['diff'], reverse=True)
    for r in sorted_res[:10]:
        report_lines.append(f"[{r['labeled']} -> {r['estimated']}] (Diff: +{r['diff']}, D0: {r['d0']:.2f}) {r['title']} ({r['file']})")
        
    report_lines.append("\n=== Worst Outliers (Top 10 Underestimated) ===")
    sorted_res = sorted(results, key=lambda x: x['diff'])
    for r in sorted_res[:10]:
        report_lines.append(f"[{r['labeled']} -> {r['estimated']}] (Diff: {r['diff']}, D0: {r['d0']:.2f}) {r['title']} ({r['file']})")

    report_content = "\n".join(report_lines)
    print(report_content)
    
    with open("batch_verification_report.txt", "w", encoding="utf-8") as f:
        f.write(report_content)
        
if __name__ == "__main__":
    target_dirs = [
        r"d:\계산기\테스트 샘플\10K2S",
        r"d:\계산기\테스트 샘플\10Key-Revive-pack"
    ]
    verify_batch_levels(target_dirs)
