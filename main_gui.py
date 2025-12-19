import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import sys

# Import our modules
import bms_parser
import osu_parser
import metric_calc
import calc
import hp_model
import new_calc  # [NEW] Linear NPS Model
import debug_osu_export  # [NEW] Debug OSU Export

class BMSCalculatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("BMS Difficulty Calculator")
        self.root.geometry("1000x800")
        
        # Developer Mode Flag
        self.is_dev_mode = "--dev" in sys.argv
        if self.is_dev_mode:
            self.root.title("BMS Difficulty Calculator (Developer Mode)")
        
        # Variables
        self.file_path = tk.StringVar()
        self.status_var = tk.StringVar(value="Ready")
        
        # Chart Metrics (Auto-filled)
        self.nps_peak = tk.DoubleVar(value=0.0)
        self.ln_ratio = tk.DoubleVar(value=0.0)
        self.jack_density = tk.DoubleVar(value=0.0)
        self.chord_avg = tk.DoubleVar(value=0.0)
        self.length_sec = tk.DoubleVar(value=0.0)
        
        # Qwilight Vars
        self.qw_pg = tk.IntVar(value=0)
        self.qw_pf = tk.IntVar(value=0)
        self.qw_gr = tk.IntVar(value=0)
        self.qw_gd = tk.IntVar(value=0)
        self.qw_bd = tk.IntVar(value=0)
        self.qw_pr = tk.IntVar(value=0)
        self.qw_result_var = tk.StringVar(value="")
        
        # HP Mode Vars
        self.hp_mode_var = tk.StringVar(value="hp9") # hp9, osu, bms_total
        
        # Parameters
        self.auto_mode_var = tk.BooleanVar(value=True)
        self.uncap_level_var = tk.BooleanVar(value=False) # Uncap Level Mode
        self.use_nps_linear_var = tk.BooleanVar(value=True) # [NEW] NPS Linear Model
        self.debug_mode_var = tk.BooleanVar(value=True) # [NEW] Debug Mode - Default ON
        
        # Default Parameters (Manual Tuned)
        self.params_manual = {
            'alpha': 0.8, 'beta': 1.0, 'gamma': 1.0, 'delta': 1.0, 'eta': 0.5, 'theta': 0.5,
            'omega': 1.5, # [NEW] Chord Weight
            'lam_L': 0.3, 'lam_S': 0.8,
            'w_F': 1.0, 'w_P': 1.0, 'w_V': 0.2,
            'a': 1.64, 'k': 0.250,
            's_offset': 3.0,
            'gamma_clear': 1.0,
            'cap_start': 60.0, 'cap_range': 30.0,
            'D_min': 0.0,     # [NEW] Level 1 Reference
            'D_max': 75.0,    # [NEW] Level 25 Reference
            'gamma_curve': 1.0 # [NEW] Level Curve Shape
        }
        
        # Scientifically Optimized Parameters (Antigravity v0.1)
        # Calibrated on GCS/10k2s Dataset (MAE 1.70)
        self.params_optimized = {
            'alpha': 0.45,
            'beta': 1.0,      # Fixed
            'gamma': 1.0,     # Fixed
            'delta': 1.0,     # Fixed
            'eta': 0.25,
            'theta': 1.101,
            'omega': 1.75,
            'lam_L': 0.4,
            'lam_S': 0.65,
            'w_F': 1.0, 'w_P': 1.0, 'w_V': 0.2,
            'a': 1.64, 'k': 0.250,
            's_offset': 0.0,
            'gamma_clear': 1.0,
            'cap_start': 60.0, 'cap_range': 30.0,
            'D_min': 11.52,   # Calibrated
            'D_max': 185.91,  # Calibrated
            'gamma_curve': 0.467 # Calibrated
        }
        
        # Current Params (Linked to UI)
        self.params = {k: tk.DoubleVar(value=v) for k, v in self.params_manual.items()}
        
        self.use_optimized_var = tk.BooleanVar(value=True) # Default to Optimized in User Mode
        if self.is_dev_mode:
            self.use_optimized_var.set(False) # Manual default in Dev Mode
        
        # Apply optimized weights by default if not dev mode
        if not self.is_dev_mode:
            self.toggle_optimized_weights()
        
        # [NEW] Store parsed data for debug export
        self.last_notes = None
        self.last_metrics = None
        self.last_file_path = None
        self.last_key_count = None  # [NEW] 파서의 키 개수 저장
            
        self._create_widgets()

    def toggle_optimized_weights(self):
        if self.use_optimized_var.get():
            target = self.params_optimized
        else:
            target = self.params_manual
            
        for k, v in target.items():
            if k in self.params:
                self.params[k].set(v)
        
    def _create_widgets(self):
        # Notebook (Tabs)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # Tab 1: Chart Analysis
        self.tab_analysis = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_analysis, text="Chart Analysis")
        self._create_analysis_tab(self.tab_analysis)
        
        # Tab 2: HP Calculator
        self.tab_hp = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_hp, text="HP Calculator (Legacy)")
        self._create_hp_tab(self.tab_hp)
        
        # Status Bar
        ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN).pack(side=tk.BOTTOM, fill=tk.X)
        
    def _create_analysis_tab(self, parent):
        # Top Frame: File Selection
        top_frame = ttk.Frame(parent, padding="10")
        top_frame.pack(fill=tk.X)
        
        ttk.Label(top_frame, text="File:").pack(side=tk.LEFT)
        ttk.Entry(top_frame, textvariable=self.file_path, width=50).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_frame, text="Browse", command=self.browse_file).pack(side=tk.LEFT)
        ttk.Button(top_frame, text="Calculate", command=self.calculate).pack(side=tk.LEFT, padx=20)
        ttk.Button(top_frame, text="🔍 Debug OSU", command=self.export_debug_osu).pack(side=tk.LEFT, padx=5)
        
        # Middle Frame: Parameters and Results
        mid_frame = ttk.Frame(parent, padding="10")
        mid_frame.pack(fill=tk.X)
        
        if self.is_dev_mode:
            # Parameters Group (Developer Only)
            param_frame = ttk.LabelFrame(mid_frame, text="Parameters (Developer Mode)", padding="10")
            param_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            
            # Parameter Descriptions
            param_descs = {
                'alpha': 'NPS Weight (Note Density)',
                'beta': 'LN Strain Weight (Long Notes)',
                'gamma': 'Jack Penalty Weight (Repeated Notes)',
                'delta': 'Roll Penalty Weight (Patterns)',
                'eta': 'Alt Cost Weight (Hand Balance)',
                'theta': 'Hand Strain Weight (One Hand Density)',
                'omega': 'Chord Weight (Chord Thickness)', # [NEW]
                'lam_L': 'Endurance EMA Lambda (Lower = Longer Memory)',
                'lam_S': 'Burst EMA Lambda (Higher = Faster Reaction)',
                'w_F': 'Endurance Weight (Overall Stamina)',
                'w_P': 'Burst Peak Weight (Max Difficulty Spike)',
                'w_V': 'Variance Weight (Difficulty Fluctuation)',
                'a': '<- 자신의 실력 숫자를 적어주세요. (10K2S 기준)',
                'k': 'Logistic Model Slope',
                's_offset': 'S Rank Difficulty Offset (OD 8)',
                'gamma_clear': 'Clear Prob Pessimism (Higher = Harder)',
                'cap_start': 'Soft Cap Start (Load Threshold)',
                'cap_range': 'Soft Cap Range (Max Add above Threshold)',
                'D_min': 'Level 1 D0 Reference',
                'D_max': 'Level 25 D0 Reference',
                'gamma_curve': 'Level Curve Gamma (>1 = Harder High Lv)',
            }

            # Grid layout for params
            row = 0
            col = 0
            for key, var in self.params.items():
                # Label
                ttk.Label(param_frame, text=key, font=('bold')).grid(row=row, column=col, sticky=tk.W, padx=5, pady=2)
                # Entry
                entry = ttk.Entry(param_frame, textvariable=var, width=8)
                entry.grid(row=row, column=col+1, padx=5, pady=2)
                if key != 'a':
                    entry.configure(state='disabled')
                else:
                    self.a_entry = entry
                    ttk.Checkbutton(param_frame, text="초딸깍 모드", variable=self.auto_mode_var, command=self.toggle_auto_mode).grid(row=row, column=col+3, padx=5)
                    ttk.Checkbutton(param_frame, text="제한 해제", variable=self.uncap_level_var).grid(row=row, column=col+4, padx=5)
                    ttk.Checkbutton(param_frame, text="최적화 가중치 사용", variable=self.use_optimized_var, command=self.toggle_optimized_weights).grid(row=row, column=col+5, padx=5)
                # Description
                desc = param_descs.get(key, "")
                ttk.Label(param_frame, text=desc, foreground="gray").grid(row=row, column=col+2, sticky=tk.W, padx=5, pady=2)
                
                row += 1
                if row > 5:
                    row = 0
                    col += 3 # Move to next set of columns (Label, Entry, Desc)
        else:
            # User Mode: Simple Guide
            guide_frame = ttk.LabelFrame(mid_frame, text="사용 가이드", padding="10")
            guide_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            
            guide_text = (
                "1. 상단의 'Browse' 버튼을 눌러 BMS/Osu 파일을 선택하세요.\n"
                "2. 'Calculate' 버튼을 누르면 난이도가 계산됩니다.\n"
                "3. 결과는 우측 텍스트 박스와 하단 그래프에 표시됩니다.\n\n"
                "* 최적화 모델 설명:\n"
                "  1. 수천 개의 차트 데이터를 학습하여 노트 밀도, 패턴, 체력 소모를 정밀 분석합니다.\n"
                "  2. 잭, 롱노트, 동시치기 등 다양한 요소를 고려해 실제 체감 난이도에 가까운 결과를 제공합니다.\n"
                "  3. Osu 파일은 타이밍 보정(+0.72)이 적용되어 최대 25.72 레벨까지 표시됩니다.\n\n"
                "* 개발자 모드로 실행하려면 '--dev' 옵션을 사용하세요."
            )
            ttk.Label(guide_frame, text=guide_text, font=("Arial", 11)).pack(anchor="w")
            
            # User Options
            opt_frame = ttk.Frame(guide_frame)
            opt_frame.pack(fill=tk.X, pady=10)
            
            ttk.Checkbutton(opt_frame, text="NPS 선형 모델 (권장)", variable=self.use_nps_linear_var).pack(side=tk.LEFT, padx=10)
            ttk.Checkbutton(opt_frame, text="레벨 제한 해제 (25+)", variable=self.uncap_level_var).pack(side=tk.LEFT, padx=10)
            ttk.Checkbutton(opt_frame, text="초딸깍 모드 (요약 팝업)", variable=self.auto_mode_var).pack(side=tk.LEFT, padx=10)
            ttk.Checkbutton(opt_frame, text="🔧 디버그 모드", variable=self.debug_mode_var).pack(side=tk.LEFT, padx=10)
                
        # Results Group
        self.result_text = tk.Text(mid_frame, height=15, width=50, font=('Consolas', 10))
        self.result_text.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10)
        
        # Bottom Frame: Graph
        bottom_frame = ttk.Frame(parent, padding="10")
        bottom_frame.pack(fill=tk.BOTH, expand=True)
        
        self.fig, self.ax = plt.subplots(figsize=(8, 4), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.fig, master=bottom_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
    def _create_hp_tab(self, parent):
        frame = ttk.Frame(parent, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="Qwilight Result to HP9 Converter", font=("Arial", 16, "bold")).pack(pady=10)
        
        # Left Side: Chart Metrics
        left_frame = ttk.LabelFrame(frame, text="Chart Metrics (Auto-filled)", padding="10")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10)
        
        metric_labels = ["Peak NPS", "LN Ratio (0-1)", "Jack Density (0-1)", "Avg Chord", "Length (sec)"]
        metric_vars = [self.nps_peak, self.ln_ratio, self.jack_density, self.chord_avg, self.length_sec]
        
        for i, (lbl, var) in enumerate(zip(metric_labels, metric_vars)):
            ttk.Label(left_frame, text=lbl).grid(row=i, column=0, padx=5, pady=5, sticky=tk.W)
            ttk.Entry(left_frame, textvariable=var, width=10).grid(row=i, column=1, padx=5, pady=5)
            
        # Right Side: Qwilight Inputs
        right_frame = ttk.LabelFrame(frame, text="Qwilight Judgments", padding="10")
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10)
        
        # HP Mode Selection
        mode_frame = ttk.Frame(right_frame)
        mode_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=5)
        ttk.Label(mode_frame, text="HP Mode:").pack(side=tk.LEFT)
        ttk.Radiobutton(mode_frame, text="HP9 (Fixed)", variable=self.hp_mode_var, value="hp9").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(mode_frame, text="Osu (Nomod)", variable=self.hp_mode_var, value="osu").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(mode_frame, text="BMS Total", variable=self.hp_mode_var, value="bms_total").pack(side=tk.LEFT, padx=5)
        
        labels = ["PGREAT (피그렛)", "PERFECT (퍼펙)", "GREAT (그레)", "GOOD (굿)", "BAD (배드)", "POOR/MISS (푸어)"]
        vars = [self.qw_pg, self.qw_pf, self.qw_gr, self.qw_gd, self.qw_bd, self.qw_pr]
        
        for i, (lbl, var) in enumerate(zip(labels, vars)):
            ttk.Label(right_frame, text=lbl, width=20, anchor="e").grid(row=i+1, column=0, padx=5, pady=5)
            ttk.Entry(right_frame, textvariable=var, width=10).grid(row=i+1, column=1, padx=5, pady=5)
            
        # Calculate Button
        ttk.Button(frame, text="Calculate Total Difficulty", command=self.calculate_total_diff).pack(side=tk.BOTTOM, pady=20)
        
        # Result
        ttk.Label(frame, textvariable=self.qw_result_var, font=("Arial", 12), justify="center").pack(side=tk.BOTTOM, pady=10)
        
    def toggle_auto_mode(self):
        if self.auto_mode_var.get():
            if hasattr(self, 'a_entry'):
                self.a_entry.configure(state='disabled')
        else:
            if hasattr(self, 'a_entry'):
                self.a_entry.configure(state='normal')

    def browse_file(self):
        filename = filedialog.askopenfilename(filetypes=[("Rhythm Game Files", "*.bms *.bme *.osu"), ("BMS Files", "*.bms *.bme"), ("Osu Files", "*.osu"), ("All Files", "*.*")])
        if filename:
            self.file_path.set(filename)
    
    def export_debug_osu(self):
        """디버그용 OSU 파일 내보내기"""
        if self.last_notes is None or self.last_metrics is None:
            messagebox.showwarning("경고", "먼저 파일을 계산해주세요.\n(Calculate 버튼 클릭)")
            return
        
        # 출력 디렉토리 선택
        output_dir = filedialog.askdirectory(title="디버그 OSU 파일 저장 위치 선택")
        if not output_dir:
            return
        
        try:
            self.status_var.set("디버그 OSU 파일 생성 중...")
            self.root.update()
            
            # 여러 모드로 생성 (키 개수 전달)
            debug_osu_export.export_multiple_modes(
                self.last_notes,
                self.last_metrics,
                self.last_file_path,
                output_dir,
                key_count=self.last_key_count
            )
            
            self.status_var.set("디버그 OSU 파일 생성 완료!")
            messagebox.showinfo(
                "완료",
                f"디버그 OSU 파일이 생성되었습니다!\n\n"
                f"위치: {output_dir}\n\n"
                f"생성된 파일:\n"
                f"- _DEBUG_local_nps.osu (로컬 NPS)\n"
                f"- _DEBUG_jack.osu (Jack 밀도)\n"
                f"- _DEBUG_chord.osu (Chord 밀도)\n"
                f"- _DEBUG_hand.osu (Hand Strain)\n"
                f"- _DEBUG_all.osu (모든 메트릭)\n\n"
                f"오스 에디터에서 열어서 확인하세요!"
            )
        except Exception as e:
            messagebox.showerror("오류", f"디버그 파일 생성 실패:\n{str(e)}")
            self.status_var.set("오류 발생")
            
    def calculate(self):
        path = self.file_path.get()
        if not path:
            messagebox.showerror("Error", "Please select a file.")
            return
            
        self.status_var.set("Parsing...")
        self.root.update()
        
        try:
            # 1. Parse
            if path.lower().endswith('.osu'):
                parser = osu_parser.OsuParser(path)
                notes = parser.parse()
                duration = parser.duration
                
                # [NEW] Filter 10K Only
                if parser.key_count != 10:
                    messagebox.showwarning("지원하지 않는 키 모드", "Osu 차트는 10키만 지원합니다.")
                    self.status_var.set("Calculation Aborted")
                    return
            else:
                parser = bms_parser.BMSParser(path)
                notes = parser.parse()
                duration = parser.duration
            
            if not notes:
                messagebox.showwarning("Warning", "No notes found in file.")
                self.status_var.set("Ready")
                return

            # Extract Metadata for HP
            self.file_total_notes = len(notes)
            if hasattr(parser, 'header'):
                self.file_hp_drain = parser.header.get('HPDrainRate', 8.0)
                self.file_total_val = parser.header.get('TOTAL', 160.0)
            else:
                self.file_hp_drain = 8.0
                self.file_total_val = 160.0
                
            self.status_var.set("Calculating Metrics...")
            self.root.update()
            
            # 2. Calculate Metrics
            metrics = metric_calc.calculate_metrics(notes, duration)
            
            # [NEW] Store data for debug export
            self.last_notes = notes
            self.last_metrics = metrics
            self.last_file_path = path
            self.last_key_count = parser.key_count if hasattr(parser, 'key_count') else None
            
            # Auto-fill Chart Metrics for HP Tab
            self.nps_peak.set(np.max(metrics['nps']))
            self.length_sec.set(duration)
            
            # Calculate LN Ratio
            ln_count = sum(1 for n in notes if n['type'] == 'ln')
            self.ln_ratio.set(ln_count / len(notes) if notes else 0)
            
            # Calculate Jack Density (Placeholder: Avg Jack Penalty / 10?)
            # Or use a simpler metric: % of notes with short interval?
            # Let's use avg jack penalty normalized
            self.jack_density.set(min(1.0, np.mean(metrics['jack_pen']) / 5.0))
            
            # Calculate Avg Chord
            # Total notes / Total timestamps?
            # Or just use NPS / (Notes/Window)? No.
            # Let's approximate: Mean(Notes per non-empty window)
            # But we only have NPS per window.
            # If NPS is 10 and window is 1s, we don't know if it's 10 singles or 2 chords of 5.
            # Let's assume Avg Chord = 1 + (NPS / 10)? Placeholder.
            self.chord_avg.set(1.0 + np.mean(metrics['nps']) / 5.0)
            
            
            self.status_var.set("Computing Difficulty...")
            self.root.update()
            
            # 3. Compute Difficulty
            # Extract params
            p = {k: v.get() for k, v in self.params.items()}
            
            # [NEW] Osu Offset
            is_osu = path.lower().endswith('.osu')
            
            # [NEW] NPS Linear Model Branch
            if self.use_nps_linear_var.get():
                # Use new_calc.py linear model
                result = new_calc.predict_from_notes(
                    notes=notes,
                    duration=duration,
                    chord_mean=np.mean(metrics['chord_strain'])
                )
                
                extra_msg = f"(NPS Linear: NPS={result['global_nps']:.1f}, std={result['nps_std']:.2f})"
                
                # Build minimal result dict for compatibility
                result_compat = {
                    'F': np.sum(metrics['nps']),
                    'P': np.max(metrics['nps']),
                    'D0': result['global_nps'],  # Use NPS as D0
                    'b_t': metrics['nps'],
                    'ema_S': metrics['nps'],
                    'ema_L': metrics['nps'],
                    'est_level': result['level'],
                    'pattern_level': result['level'],
                    'level_label': result['label'],
                    # [NEW] Include NPS metrics from new_calc
                    'peak_nps': result['peak_nps'],
                    'global_nps': result['global_nps'],
                    'nps_std': result['nps_std']
                }
                result = result_compat
                
                if self.auto_mode_var.get():
                    popup_msg = f"이 패턴의 추정 레벨은 {result['est_level']} 입니다."
                    messagebox.showinfo("초딸깍 요약", popup_msg)
            
            else:
                # Legacy complex model
                lvl_offset = 0.72 if is_osu else 0.0
                result = calc.compute_map_difficulty(
                    metrics['nps'], metrics['ln_strain'], metrics['jack_pen'], 
                    metrics['roll_pen'], metrics['alt_cost'], metrics['hand_strain'],
                    metrics['chord_strain'],
                    alpha=p['alpha'], beta=p['beta'], gamma=p['gamma'], delta=p['delta'], eta=p['eta'], theta=p['theta'],
                    omega=p['omega'],
                    lam_L=p['lam_L'], lam_S=p['lam_S'],
                    w_F=p['w_F'], w_P=p['w_P'], w_V=p['w_V'],
                    a=p['a'], k=p['k'],
                    duration=duration,
                    s_offset=p['s_offset'],
                    total_notes=len(notes),
                    gamma_clear=p['gamma_clear'],
                    cap_start=p['cap_start'], cap_range=p['cap_range'],
                    uncap_level=self.uncap_level_var.get(),
                    D_min=p['D_min'],
                    D_max=p['D_max'], gamma_curve=p['gamma_curve'],
                    level_offset=lvl_offset
                )
                extra_msg = f"(Legacy Model: D0={result['D0']:.1f})"
                
                if self.auto_mode_var.get():
                    popup_msg = f"이 패턴의 추정 레벨은 {result['est_level']} 입니다."
                    messagebox.showinfo("초딸깍 요약", popup_msg)
            
            # 4. Display Results
            # Calculate NPS statistics
            import os
            
            # NPS Linear 모델 사용 시 new_calc의 Peak NPS 사용
            if self.use_nps_linear_var.get() and 'peak_nps' in result:
                global_nps = result['global_nps']
                peak_nps = result['peak_nps']  # ±500ms Local NPS
                avg_nps = np.mean(metrics['nps'])
                nps_std = result['nps_std']
            else:
                # Legacy 모델 사용 시 기존 방식
                global_nps = len(notes) / duration
                avg_nps = np.mean(metrics['nps'])
                peak_nps = np.max(metrics['nps'])  # 1초 윈도우 기준
                nps_std = np.std(metrics['nps'])
            
            # Get key count
            key_count = parser.key_count if hasattr(parser, 'key_count') else '?'
            
            # Calculate HP9 Max Misses
            max_misses = hp_model.calculate_max_misses(len(notes))
            
            # Build result string with improved formatting
            res_str = "═" * 50 + "\n"
            res_str += f"📁 파일: {os.path.basename(path)}\n"
            res_str += f"🎹 키모드: {key_count}K\n"
            res_str += "═" * 50 + "\n\n"
            
            res_str += "📊 기본 지표\n"
            res_str += "─" * 50 + "\n"
            res_str += f"  총 노트수      : {len(notes):,}개\n"
            res_str += f"  곡 길이        : {duration:.2f}초 ({duration/60:.2f}분)\n"
            res_str += f"  Global NPS     : {global_nps:.2f}\n"
            
            # Peak NPS 표시 (모델에 따라 다른 설명)
            if self.use_nps_linear_var.get():
                res_str += f"  Peak NPS       : {peak_nps}개 (±500ms Local)\n"
            else:
                res_str += f"  Peak NPS       : {peak_nps:.2f} (1초 윈도우)\n"
            
            res_str += f"  평균 NPS       : {avg_nps:.2f}\n"
            res_str += f"  NPS 표준편차   : {nps_std:.2f}\n\n"
            
            res_str += "🎯 난이도 분석\n"
            res_str += "─" * 50 + "\n"
            model_name = 'NPS Linear' if self.use_nps_linear_var.get() else 'Legacy Complex'
            res_str += f"  사용 모델      : {model_name}\n"
            res_str += f"  Endurance (F)  : {result['F']:.2f}\n"
            res_str += f"  Burst Peak (P) : {result['P']:.2f}\n"
            res_str += f"  Raw Diff (D0)  : {result['D0']:.2f}\n"
            res_str += f"  추정 레벨      : {result['est_level']} ({result['level_label']})\n"
            if extra_msg:
                res_str += f"  {extra_msg}\n"
            res_str += "\n"
            
            res_str += "💚 HP9 참고 정보\n"
            res_str += "─" * 50 + "\n"
            res_str += f"  최대 허용 미스 : ~{max_misses}개\n"
            res_str += "  (나머지 모두 300s 가정)\n"
            
            # [NEW] Debug Mode: Show detailed metrics
            if self.debug_mode_var.get():
                res_str += "\n"
                res_str += "🔧 디버그 정보 (상세)\n"
                res_str += "═" * 50 + "\n\n"
                
                # Note type distribution
                note_types = {}
                for note in notes:
                    note_type = note.get('type', 'unknown')
                    note_types[note_type] = note_types.get(note_type, 0) + 1
                
                res_str += "📝 노트 타입 분포\n"
                res_str += "─" * 50 + "\n"
                for ntype, count in sorted(note_types.items()):
                    percentage = (count / len(notes) * 100) if notes else 0
                    res_str += f"  {ntype:15s}: {count:5,d}개 ({percentage:5.2f}%)\n"
                res_str += "\n"
                
                # Metrics statistics
                res_str += "📊 Metrics 통계\n"
                res_str += "─" * 50 + "\n"
                metric_names = ['nps', 'ln_strain', 'jack_pen', 'roll_pen', 'alt_cost', 'hand_strain', 'chord_strain']
                for metric_name in metric_names:
                    if metric_name in metrics:
                        metric_values = metrics[metric_name]
                        res_str += f"\n  {metric_name}:\n"
                        res_str += f"    최소값    : {np.min(metric_values):.4f}\n"
                        res_str += f"    최대값    : {np.max(metric_values):.4f}\n"
                        res_str += f"    평균      : {np.mean(metric_values):.4f}\n"
                        res_str += f"    중앙값    : {np.median(metric_values):.4f}\n"
                        res_str += f"    표준편차  : {np.std(metric_values):.4f}\n"
                res_str += "\n"
                
                # Window-by-window details (first 10 and last 10)
                res_str += "🔍 윈도우별 상세 (처음 10개)\n"
                res_str += "─" * 50 + "\n"
                res_str += f"{'Win':>4s} {'NPS':>6s} {'LN':>6s} {'Jack':>6s} {'Roll':>6s} {'Alt':>6s} {'Hand':>6s} {'Chord':>6s}\n"
                res_str += "─" * 50 + "\n"
                for i in range(min(10, len(metrics['nps']))):
                    res_str += f"{i:4d} "
                    res_str += f"{metrics['nps'][i]:6.2f} "
                    res_str += f"{metrics['ln_strain'][i]:6.2f} "
                    res_str += f"{metrics['jack_pen'][i]:6.2f} "
                    res_str += f"{metrics['roll_pen'][i]:6.2f} "
                    res_str += f"{metrics['alt_cost'][i]:6.2f} "
                    res_str += f"{metrics['hand_strain'][i]:6.2f} "
                    res_str += f"{metrics['chord_strain'][i]:6.2f}\n"
                
                if len(metrics['nps']) > 20:
                    res_str += "  ...\n"
                    res_str += "\n🔍 윈도우별 상세 (마지막 10개)\n"
                    res_str += "─" * 50 + "\n"
                    res_str += f"{'Win':>4s} {'NPS':>6s} {'LN':>6s} {'Jack':>6s} {'Roll':>6s} {'Alt':>6s} {'Hand':>6s} {'Chord':>6s}\n"
                    res_str += "─" * 50 + "\n"
                    for i in range(max(0, len(metrics['nps'])-10), len(metrics['nps'])):
                        res_str += f"{i:4d} "
                        res_str += f"{metrics['nps'][i]:6.2f} "
                        res_str += f"{metrics['ln_strain'][i]:6.2f} "
                        res_str += f"{metrics['jack_pen'][i]:6.2f} "
                        res_str += f"{metrics['roll_pen'][i]:6.2f} "
                        res_str += f"{metrics['alt_cost'][i]:6.2f} "
                        res_str += f"{metrics['hand_strain'][i]:6.2f} "
                        res_str += f"{metrics['chord_strain'][i]:6.2f}\n"
                
                res_str += "\n"
                
                # Model parameters used
                if not self.use_nps_linear_var.get():
                    res_str += "⚙️ 사용된 모델 파라미터\n"
                    res_str += "─" * 50 + "\n"
                    p = {k: v.get() for k, v in self.params.items()}
                    for key, value in sorted(p.items()):
                        res_str += f"  {key:15s}: {value:.4f}\n"
                    res_str += "\n"
                
                # Parser-specific info
                res_str += "📄 파서 상세 정보\n"
                res_str += "─" * 50 + "\n"
                if hasattr(parser, 'header'):
                    res_str += "  헤더 정보:\n"
                    for key, value in list(parser.header.items())[:10]:
                        res_str += f"    {key}: {value}\n"
                if hasattr(parser, 'bpm_definitions') and parser.bpm_definitions:
                    res_str += f"\n  BPM 정의: {len(parser.bpm_definitions)}개\n"
                    for bpm_key, bpm_val in list(parser.bpm_definitions.items())[:5]:
                        res_str += f"    {bpm_key}: {bpm_val}\n"
                res_str += "\n"
            
            self.result_text.delete(1.0, tk.END)
            self.result_text.insert(tk.END, res_str)
            
            # 5. Plot
            self.ax.clear()
            t = np.arange(len(result['b_t'])) # Assuming 1s windows
            self.ax.plot(t, result['b_t'], label='Load (b_t)', alpha=0.5)
            self.ax.plot(t, result['ema_S'], label='EMA_S (Burst)', linestyle='--')
            self.ax.plot(t, result['ema_L'], label='EMA_L (Endurance)', linestyle=':')
            self.ax.set_title("Difficulty Load over Time")
            self.ax.set_xlabel("Time (s)")
            self.ax.set_ylabel("Load")
            self.ax.legend()
            self.canvas.draw()
            
            self.status_var.set("Calculation Complete.")
            
        except Exception as e:
            messagebox.showerror("Error", str(e))
            self.status_var.set("Error occurred.")
            print(e)
            
    def calculate_total_diff(self):
        try:
            res = calc.total_difficulty_10k(
                nps_peak=self.nps_peak.get(),
                ln_ratio=self.ln_ratio.get(),
                jack_density=self.jack_density.get(),
                chord_avg=self.chord_avg.get(),
                length_sec=self.length_sec.get(),
                n_pg=self.qw_pg.get(),
                n_pf=self.qw_pf.get(),
                n_gr=self.qw_gr.get(),
                n_gd=self.qw_gd.get(),
                n_bd=self.qw_bd.get(),
                n_poor=self.qw_pr.get(),
                # Dynamic HP Params
                hp_start=10.0, # Default start?
            )
            
            # Recalculate HP End using correct mode
            hp_end = hp_model.hp9_from_qwilight(
                n_pg=self.qw_pg.get(),
                n_pf=self.qw_pf.get(),
                n_gr=self.qw_gr.get(),
                n_gd=self.qw_gd.get(),
                n_bd=self.qw_bd.get(),
                n_poor=self.qw_pr.get(),
                hp_start=10.0 if self.hp_mode_var.get() != 'osu' else 10.0, # Osu starts full? Our model handles it.
                mode=self.hp_mode_var.get(),
                hp_drain=self.file_hp_drain,
                total_val=self.file_total_val,
                total_notes=self.file_total_notes
            )
            
            # Update result dictionary manually since total_difficulty_10k uses fixed HP9
            res['hp_end'] = hp_end
            
            # Recalculate Factor
            # HP Factor logic needs to adapt to mode?
            # For now, let's keep the factor logic based on "Surviving HP9" scale.
            # If mode is Osu/BMS, we normalized output to be >0 = Clear.
            # So we can map it similarly.
            # HP9: Max ~20? End > 0.
            # Osu: Max 10. End > 0.
            # BMS: Max 100? End > 0 (Shifted).
            
            # Let's normalize hp_end to [0, 1] relative to max possible?
            # Or just use the sign.
            # Existing factor: m = hp_end / hp_start.
            # If hp_end is large positive -> Easy.
            
            hp_start_val = 10.0
            if self.hp_mode_var.get() == 'bms_total':
                hp_start_val = 20.0 # BMS starts at 20 usually? But we shifted result.
                # Result is (Gauge - 80). Max gauge 100 -> Max result 20.
                # Min gauge 0 -> Min result -80.
                # So range is similar to HP9 (10 to -10).
                pass
            
            res['hp_factor'] = calc.hp_difficulty_factor_from_hp9(hp_end, hp_start=hp_start_val)
            res['total_diff'] = res['pattern_diff'] * res['hp_factor']
            res['level'] = math.sqrt(res['total_diff'])
            
            status = "SURVIVED" if res['hp_end'] > 0 else "FAILED"
            
            out = f"HP Status: {status} (HP: {res['hp_end']:.2f})\n"
            out += f"Pattern Diff: {res['pattern_diff']:.2f}\n"
            out += f"HP Factor: {res['hp_factor']:.2f}x\n"
            out += f"Total Diff: {res['total_diff']:.2f}\n"
            out += f"Final Level: {res['level']:.2f}"
            
            self.qw_result_var.set(out)
                
        except Exception as e:
            self.qw_result_var.set("Error in input")
            print(e)

if __name__ == "__main__":
    root = tk.Tk()
    app = BMSCalculatorApp(root)
    root.mainloop()
