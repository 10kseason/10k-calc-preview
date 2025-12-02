
import os
import json
import time
import numpy as np
import bms_parser
import osu_parser
import calc
import metric_calc
import gc

def run_analysis():
    # 1. Setup Paths
    target_dirs = [
        r"d:\계산기\테스트 샘플",
        r"d:\계산기\패턴 모음",
        r"d:\계산기\패턴 모음2(GCS)",
        r"d:\계산기\osu 폴더 전체"
    ]
    
    # 2. Load Optimizer Params
    opt_params = {}
    try:
        with open(r"d:\계산기\final_params.json", "r", encoding='utf-8') as f:
            opt_params = json.load(f)
        print("Loaded optimizer params from final_params.json")
    except Exception as e:
        print(f"Could not load final_params.json: {e}")
        print("Will skip optimizer comparison if params are missing.")

    # 3. Scan Files (Load all into list)
    print("Scanning files (Basic Mode)...")
    files = []
    extensions = {'.bms', '.bme', '.bml', '.osu'}
    
    for root_dir in target_dirs:
        for root, dirs, filenames in os.walk(root_dir):
            for filename in filenames:
                if os.path.splitext(filename)[1].lower() in extensions:
                    files.append(os.path.join(root, filename))
                    
    print(f"Found {len(files)} files.")
    
    results = []
    start_time = time.time()
    
    for i, file_path in enumerate(files):
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
            
            # Extract Metadata
            key_count = parser.key_count
            duration = parser.duration
            header_title = parser.header.get('Title', 'Unknown') if is_osu else "Unknown"
            
            # Get Label (if BMS)
            label = None
            title = header_title
            
            if not is_osu:
                # Use parser's header
                try:
                    if 'PLAYLEVEL' in parser.header:
                        label = int(parser.header['PLAYLEVEL'])
                    if 'TITLE' in parser.header:
                        title = parser.header['TITLE']
                except: pass
            
            # We can delete parser now to save some memory, but keep notes
            del parser
            
            if not notes:
                continue
                
            # Filter 10K Only
            if is_osu and key_count != 10:
                continue
                
            if duration < 10:
                continue
            
            # GCS Filtering Rules
            if is_gcs:
                if label is None or label == 0:
                    continue 
                label = label - 5
                if label < 1:
                    continue
                            
            # Calculate Metrics
            metrics = metric_calc.calculate_metrics(notes, duration)
            del notes # Free notes
            
            # Osu Offset
            lvl_offset = 0.72 if is_osu else 0.0
            
            # 1. Current Values
            res_curr = calc.compute_map_difficulty(
                metrics['nps'], metrics['ln_strain'], metrics['jack_pen'], 
                metrics['roll_pen'], metrics['alt_cost'], metrics['hand_strain'],
                metrics['chord_strain'],
                duration=duration,
                total_notes=0,
                uncap_level=True,
                level_offset=lvl_offset
            )
            
            # 2. Optimizer Values
            res_opt = None
            if opt_params:
                res_opt = calc.compute_map_difficulty(
                    metrics['nps'], metrics['ln_strain'], metrics['jack_pen'], 
                    metrics['roll_pen'], metrics['alt_cost'], metrics['hand_strain'],
                    metrics['chord_strain'],
                    alpha=opt_params.get('alpha', 0.8),
                    theta=opt_params.get('theta', 0.5),
                    eta=opt_params.get('eta', 0.5),
                    omega=opt_params.get('omega', 1.5),
                    lam_L=opt_params.get('lam_L', 0.3),
                    lam_S=opt_params.get('lam_S', 0.8),
                    D_max=opt_params.get('D_max', 55.0),
                    gamma_curve=opt_params.get('gamma_curve', 1.0),
                    duration=duration,
                    total_notes=0,
                    uncap_level=True,
                    level_offset=lvl_offset
                )
                
            results.append({
                'file': os.path.basename(file_path),
                'title': title,
                'label': label,
                'curr_level': res_curr['pattern_level'],
                'curr_d0': res_curr['D0'],
                'opt_level': res_opt['pattern_level'] if res_opt else 0,
                'opt_d0': res_opt['D0'] if res_opt else 0
            })
            
            if i % 100 == 0:
                print(f"Processed {i}/{len(files)}...", flush=True)
                
        except Exception as e:
            # print(f"Error {file_path}: {e}")
            pass

    end_time = time.time()
    total_time = end_time - start_time
    avg_time_per_file = total_time / len(results) if results else 0
    
    # Generate Report
    report_lines = []
    report_lines.append("=== Detailed Global Estimation Report (Basic Mode) ===")
    report_lines.append(f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append(f"Total Files Found: {len(files)}")
    report_lines.append(f"Total Files Processed: {len(results)}")
    report_lines.append(f"Total Execution Time: {total_time:.2f}s")
    report_lines.append(f"Average Time per File: {avg_time_per_file*1000:.2f}ms")
    
    # Helper for stats
    def get_stats(data, key):
        vals = [r[key] for r in data]
        if not vals: return "N/A"
        return (
            f"Mean: {np.mean(vals):.2f} | Median: {np.median(vals):.2f} | "
            f"Min: {np.min(vals):.2f} | Max: {np.max(vals):.2f} | Std: {np.std(vals):.2f}"
        )

    # Split Data
    labeled_data = [r for r in results if r['label'] is not None]
    unlabeled_data = [r for r in results if r['label'] is None]
    
    report_lines.append("\n--- Global Statistics (All Files) ---")
    report_lines.append(f"Current Level:   {get_stats(results, 'curr_level')}")
    if opt_params:
        report_lines.append(f"Optimizer Level: {get_stats(results, 'opt_level')}")

    report_lines.append(f"\n--- Labeled Files ({len(labeled_data)}) ---")
    report_lines.append(f"Current Level:   {get_stats(labeled_data, 'curr_level')}")
    if opt_params:
        report_lines.append(f"Optimizer Level: {get_stats(labeled_data, 'opt_level')}")
        curr_mae = np.mean([abs(r['curr_level'] - r['label']) for r in labeled_data])
        opt_mae = np.mean([abs(r['opt_level'] - r['label']) for r in labeled_data])
        report_lines.append(f"MAE Comparison: Current={curr_mae:.2f} vs Optimizer={opt_mae:.2f}")

    report_lines.append(f"\n--- Unlabeled Files ({len(unlabeled_data)}) ---")
    report_lines.append(f"Current Level:   {get_stats(unlabeled_data, 'curr_level')}")
    if opt_params:
        report_lines.append(f"Optimizer Level: {get_stats(unlabeled_data, 'opt_level')}")

    # Distribution Histogram
    def make_hist(data, key, bins=10):
        vals = [r[key] for r in data]
        hist, bin_edges = np.histogram(vals, bins=bins, range=(0, 26))
        lines = []
        for i in range(len(hist)):
            range_str = f"{int(bin_edges[i]):02d}-{int(bin_edges[i+1]):02d}"
            bar = "#" * int(hist[i] / len(data) * 50) 
            lines.append(f"{range_str} : {hist[i]:4d} ({hist[i]/len(data)*100:5.1f}%) | {bar}")
        return "\n".join(lines)

    report_lines.append("\n--- Level Distribution (All Files) ---")
    report_lines.append("[Current Default]")
    report_lines.append(make_hist(results, 'curr_level', bins=13)) 
    
    if opt_params:
        report_lines.append("\n[Optimizer]")
        report_lines.append(make_hist(results, 'opt_level', bins=13))

    # Detailed List (Top 30 by Optimizer Level)
    if opt_params:
        report_lines.append("\n=== Top 30 Hardest (Optimizer) ===")
        sorted_by_opt = sorted(results, key=lambda x: x['opt_level'], reverse=True)
        for r in sorted_by_opt[:30]:
            lbl = f"[Lv.{r['label']}]" if r['label'] else "[Unlabeled]"
            report_lines.append(f"{r['opt_level']:.2f} {lbl} {r['title']} ({r['file']})")

    # Full List of All Files
    report_lines.append("\n=== All Files List (Sorted by Optimizer Level) ===")
    report_lines.append("OptLevel | CurrLevel | Label | Title | File")
    sorted_all = sorted(results, key=lambda x: x['opt_level'] if opt_params else x['curr_level'], reverse=True)
    for r in sorted_all:
        lbl = str(r['label']) if r['label'] is not None else "N/A"
        line = f"{r['opt_level']:8.2f} | {r['curr_level']:9.2f} | {lbl:>5} | {r['title']} | {r['file']}"
        report_lines.append(line)

    report_content = "\n".join(report_lines)
    print(report_content)
    
    with open("full_analysis_report_basic.txt", "w", encoding="utf-8") as f:
        f.write(report_content)

if __name__ == "__main__":
    print("Starting script...", flush=True)
    run_analysis()
