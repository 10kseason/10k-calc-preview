
import os
import json
import time
import numpy as np
import bms_parser
import osu_parser
import calc
import metric_calc
import gc

def scan_files(target_dirs):
    """Generator that yields file paths from target directories."""
    extensions = {'.bms', '.bme', '.bml', '.osu'}
    for root_dir in target_dirs:
        for root, dirs, files in os.walk(root_dir):
            for file in files:
                if os.path.splitext(file)[1].lower() in extensions:
                    yield os.path.join(root, file)

def get_bms_metadata(file_path, parser_header):
    """Robustly extract BMS metadata."""
    label = None
    title = parser_header.get('TITLE', 'Unknown')
    
    # Try parser first
    if 'PLAYLEVEL' in parser_header:
        try:
            label = int(parser_header['PLAYLEVEL'])
        except: pass
        
    # If missing, try manual read (sometimes parser misses headers if encoding issues)
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
    # 1. Setup Paths
    target_dirs = [
        r"d:\계산기\테스트 샘플",
        r"d:\계산기\패턴 모음",
        r"d:\계산기\패턴 모음2(GCS)",
        r"d:\계산기\osu 폴더 전체"
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
    print("Starting analysis (Global Optimization)...")
    temp_file = "analysis_results.jsonl"
    
    # Clear previous temp file
    if os.path.exists(temp_file):
        os.remove(temp_file)
        
    start_time = time.time()
    count = 0
    
    with open(temp_file, "w", encoding="utf-8") as f_out:
        for file_path in scan_files(target_dirs):
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
                header_copy = parser.header.copy() if hasattr(parser, 'header') else {}
                
                del parser 
                
                if not notes: continue
                if is_osu and key_count != 10: continue
                if duration < 10: continue
                
                # Get Label & Title
                if is_osu:
                    title = header_copy.get('Title', 'Unknown')
                    label = None
                else:
                    title, label = get_bms_metadata(file_path, header_copy)
                
                # GCS Filtering Rules
                if is_gcs:
                    if label is None or label == 0: continue 
                    label = label - 5
                    if label < 1: continue
                                
                # Calculate Metrics
                metrics = metric_calc.calculate_metrics(notes, duration)
                del notes
                
                # Osu Offset
                lvl_offset = 0.72 if is_osu else 0.0
                
                # --- Analyzer: Optimized ---
                # Use params from final_params.json
                p = final_params
                res_opt = calc.compute_map_difficulty(
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
                    total_notes=0, 
                    uncap_level=True,
                    level_offset=lvl_offset
                )
                
                result_entry = {
                    'file': os.path.basename(file_path),
                    'full_path': file_path,
                    'title': title,
                    'label': label,
                    'opt_level': res_opt['pattern_level'],
                    'opt_d0': res_opt['D0']
                }
                
                f_out.write(json.dumps(result_entry) + "\n")
                
                count += 1
                if count % 100 == 0:
                    print(f"Processed {count} files...", flush=True)
                    gc.collect()
                    
            except Exception as e:
                pass

    end_time = time.time()
    total_time = end_time - start_time
    
    # 4. Generate Reports
    print("Generating reports...")
    results = []
    with open(temp_file, "r", encoding="utf-8") as f_in:
        for line in f_in:
            results.append(json.loads(line))
            
    # Helper for stats
    def get_stats(data, key):
        vals = [r[key] for r in data if r[key] is not None and not np.isnan(r[key])]
        if not vals: return "N/A"
        return (
            f"Mean: {np.mean(vals):.2f} | Median: {np.median(vals):.2f} | "
            f"Min: {np.min(vals):.2f} | Max: {np.max(vals):.2f} | Std: {np.std(vals):.2f}"
        )

    def make_hist(data, key, bins=20):
        vals = [r[key] for r in data if r[key] is not None and not np.isnan(r[key])]
        if not vals: return "No data"
        
        max_val = max(np.max(vals), 26) # At least 26 to cover normal range
        hist, bin_edges = np.histogram(vals, bins=bins, range=(0, max_val))
        lines = []
        for i in range(len(hist)):
            range_str = f"{int(bin_edges[i]):03d}-{int(bin_edges[i+1]):03d}"
            bar_len = int(hist[i] / len(vals) * 50) if len(vals) > 0 else 0
            bar = "#" * bar_len
            lines.append(f"{range_str} : {hist[i]:4d} ({hist[i]/len(vals)*100:5.1f}%) | {bar}")
        return "\n".join(lines)

    # --- Report: Optimized ---
    lines_opt = []
    lines_opt.append("=== Analysis Report: Band-wise Optimized (Antigravity v0.1) ===")
    lines_opt.append(f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines_opt.append(f"Total Files: {len(results)}")
    lines_opt.append(f"Execution Time: {total_time:.2f}s")
    
    labeled = [r for r in results if r['label'] is not None]
    
    lines_opt.append("\n--- Statistics ---")
    lines_opt.append(f"All Files Level:   {get_stats(results, 'opt_level')}")
    lines_opt.append(f"Labeled Files:     {get_stats(labeled, 'opt_level')}")
    if labeled:
        mae = np.mean([abs(r['opt_level'] - r['label']) for r in labeled])
        lines_opt.append(f"MAE (vs Label):    {mae:.2f}")
    
    lines_opt.append("\n--- Level Distribution ---")
    lines_opt.append(make_hist(results, 'opt_level', bins=20))
    
    lines_opt.append("\n=== Top 30 Hardest ===")
    sorted_opt = sorted(results, key=lambda x: x['opt_level'], reverse=True)
    for r in sorted_opt[:30]:
        lbl = f"[Lv.{r['label']}]" if r['label'] else "[Unlabeled]"
        lines_opt.append(f"{r['opt_level']:.2f} {lbl} {r['title']} ({r['file']})")

    lines_opt.append("\n=== All Files List ===")
    lines_opt.append("Level | Label | Title | File")
    for r in sorted_opt:
        lbl = str(r['label']) if r['label'] is not None else "N/A"
        lines_opt.append(f"{r['opt_level']:6.2f} | {lbl:>5} | {r['title']} | {r['file']}")
        
    with open("report_optimized.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(lines_opt))

    print("Reports generated: report_optimized.txt")

if __name__ == "__main__":
    run_analysis()
