import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# Import our modules
import bms_parser
import osu_parser
import metric_calc
import calc
import hp_model

class BMSCalculatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("BMS Difficulty Calculator")
        self.root.geometry("1000x800")
        
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
        
        # Parameters
        self.auto_mode_var = tk.BooleanVar(value=False)
        self.params = {
            'alpha': tk.DoubleVar(value=0.7),
            'beta': tk.DoubleVar(value=1.5),
            'gamma': tk.DoubleVar(value=0.5),
            'delta': tk.DoubleVar(value=1.0),
            'eta': tk.DoubleVar(value=1.0),
            'theta': tk.DoubleVar(value=1.5),
            'lam_L': tk.DoubleVar(value=0.3),
            'lam_S': tk.DoubleVar(value=0.5),
            'w_F': tk.DoubleVar(value=0.75),
            'w_P': tk.DoubleVar(value=0.5),
            'w_V': tk.DoubleVar(value=-0.1),
            'a': tk.DoubleVar(value=7),
            'a': tk.DoubleVar(value=7),
            'k': tk.DoubleVar(value=0.004),
            's_offset': tk.DoubleVar(value=3.0),
        }
        
        self._create_widgets()
        
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
        self.notebook.add(self.tab_hp, text="HP Calculator (Qwilight)")
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
        
        # Middle Frame: Parameters and Results
        mid_frame = ttk.Frame(parent, padding="10")
        mid_frame.pack(fill=tk.X)
        
        # Parameters Group
        param_frame = ttk.LabelFrame(mid_frame, text="Parameters", padding="10")
        param_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Parameter Descriptions
        param_descs = {
            'alpha': 'NPS Weight (Note Density)',
            'beta': 'LN Strain Weight (Long Notes)',
            'gamma': 'Jack Penalty Weight (Repeated Notes)',
            'delta': 'Roll Penalty Weight (Patterns)',
            'eta': 'Alt Cost Weight (Hand Balance)',
            'theta': 'Hand Strain Weight (One Hand Density)',
            'lam_L': 'Endurance EMA Lambda (Lower = Longer Memory)',
            'lam_S': 'Burst EMA Lambda (Higher = Faster Reaction)',
            'w_F': 'Endurance Weight (Overall Stamina)',
            'w_P': 'Burst Peak Weight (Max Difficulty Spike)',
            'w_V': 'Variance Weight (Difficulty Fluctuation)',
            'a': '<- 자신의 실력 숫자를 적어주세요. (10K2S 기준)',
            'a': '<- 자신의 실력 숫자를 적어주세요. (10K2S 기준)',
            'k': 'Logistic Model Slope',
            's_offset': 'S Rank Difficulty Offset (OD 8)',
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
                ttk.Checkbutton(param_frame, text="Auto", variable=self.auto_mode_var, command=self.toggle_auto_mode).grid(row=row, column=col+3, padx=5)
            # Description
            desc = param_descs.get(key, "")
            ttk.Label(param_frame, text=desc, foreground="gray").grid(row=row, column=col+2, sticky=tk.W, padx=5, pady=2)
            
            row += 1
            if row > 5:
                row = 0
                col += 3 # Move to next set of columns (Label, Entry, Desc)
                
        # Results Group
        self.result_text = tk.Text(mid_frame, height=10, width=40)
        self.result_text.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10)
        
        # Bottom Frame: Graph
        bottom_frame = ttk.Frame(parent, padding="10")
        bottom_frame.pack(fill=tk.BOTH, expand=True)
        
        self.fig, self.ax = plt.subplots(figsize=(8, 4))
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
        
        labels = ["PGREAT (피그렛)", "PERFECT (퍼펙)", "GREAT (그레)", "GOOD (굿)", "BAD (배드)", "POOR/MISS (푸어)"]
        vars = [self.qw_pg, self.qw_pf, self.qw_gr, self.qw_gd, self.qw_bd, self.qw_pr]
        
        for i, (lbl, var) in enumerate(zip(labels, vars)):
            ttk.Label(right_frame, text=lbl, width=20, anchor="e").grid(row=i, column=0, padx=5, pady=5)
            ttk.Entry(right_frame, textvariable=var, width=10).grid(row=i, column=1, padx=5, pady=5)
            
        # Calculate Button
        ttk.Button(frame, text="Calculate Total Difficulty", command=self.calculate_total_diff).pack(side=tk.BOTTOM, pady=20)
        
        # Result
        ttk.Label(frame, textvariable=self.qw_result_var, font=("Arial", 12), justify="center").pack(side=tk.BOTTOM, pady=10)
        
    def toggle_auto_mode(self):
        if self.auto_mode_var.get():
            self.a_entry.configure(state='disabled')
        else:
            self.a_entry.configure(state='normal')

    def browse_file(self):
        filename = filedialog.askopenfilename(filetypes=[("Rhythm Game Files", "*.bms *.bme *.osu"), ("BMS Files", "*.bms *.bme"), ("Osu Files", "*.osu"), ("All Files", "*.*")])
        if filename:
            self.file_path.set(filename)
            
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
            else:
                parser = bms_parser.BMSParser(path)
                notes = parser.parse()
                duration = parser.duration
            
            if not notes:
                messagebox.showwarning("Warning", "No notes found in file.")
                self.status_var.set("Ready")
                return
                
            self.status_var.set("Calculating Metrics...")
            self.root.update()
            
            # 2. Calculate Metrics
            metrics = metric_calc.calculate_metrics(notes, duration)
            
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
            
            if self.auto_mode_var.get():
                found_a_clear = None
                found_a_s_rank = None
                
                for a_val in range(1, 20):
                    p['a'] = float(a_val)
                    result = calc.compute_map_difficulty(
                        metrics['nps'], metrics['ln_strain'], metrics['jack_pen'], 
                        metrics['roll_pen'], metrics['alt_cost'], metrics['hand_strain'],
                        alpha=p['alpha'], beta=p['beta'], gamma=p['gamma'], delta=p['delta'], eta=p['eta'], theta=p['theta'],
                        lam_L=p['lam_L'], lam_S=p['lam_S'],
                        w_F=p['w_F'], w_P=p['w_P'], w_V=p['w_V'],
                        a=p['a'], k=p['k'],
                        duration=duration,
                        s_offset=p['s_offset']
                    )
                    
                    if found_a_clear is None and result['S_hat'] >= 0.75:
                        found_a_clear = a_val
                        
                    if found_a_s_rank is None and result['S_rank_prob'] >= 0.75:
                        found_a_s_rank = a_val
                        
                    if found_a_clear is not None and found_a_s_rank is not None:
                        break
                
                # Fallbacks
                if found_a_clear is None: found_a_clear = 19
                if found_a_s_rank is None: found_a_s_rank = 19
                    
                # Re-run with found_a_clear (or maybe we should show results for the clear level?)
                # Let's use found_a_clear for the main display
                p['a'] = float(found_a_clear)
                result = calc.compute_map_difficulty(
                    metrics['nps'], metrics['ln_strain'], metrics['jack_pen'], 
                    metrics['roll_pen'], metrics['alt_cost'], metrics['hand_strain'],
                    alpha=p['alpha'], beta=p['beta'], gamma=p['gamma'], delta=p['delta'], eta=p['eta'], theta=p['theta'],
                    lam_L=p['lam_L'], lam_S=p['lam_S'],
                    w_F=p['w_F'], w_P=p['w_P'], w_V=p['w_V'],
                    a=p['a'], k=p['k'],
                    duration=duration,
                    s_offset=p['s_offset']
                )
                
                extra_msg = f"({found_a_clear}부터 클리어 가능성이 75% 입니다. 즉 이 차트의 레벨은 {found_a_clear}입니다.)\n"
                extra_msg += f"({found_a_s_rank}부터 S랭크 가능성이 75% 입니다. 즉 이 차트의 S랭크 레벨은 {found_a_s_rank}입니다.)"
            else:
                result = calc.compute_map_difficulty(
                    metrics['nps'], metrics['ln_strain'], metrics['jack_pen'], 
                    metrics['roll_pen'], metrics['alt_cost'], metrics['hand_strain'],
                    alpha=p['alpha'], beta=p['beta'], gamma=p['gamma'], delta=p['delta'], eta=p['eta'], theta=p['theta'],
                    lam_L=p['lam_L'], lam_S=p['lam_S'],
                    w_F=p['w_F'], w_P=p['w_P'], w_V=p['w_V'],
                    a=p['a'], k=p['k'],
                    duration=duration,
                    s_offset=p['s_offset']
                )
                extra_msg = ""
            
            # 4. Display Results
            # Calculate HP9 Max Misses
            max_misses = hp_model.calculate_max_misses(len(notes))
            
            res_str = f"Results for {path.split('/')[-1]}\n"
            res_str += "-" * 30 + "\n"
            res_str += f"Duration: {duration:.2f}s\n"
            res_str += f"Notes: {len(notes)}\n"
            res_str += f"Endurance (F): {result['F']:.2f}\n"
            res_str += f"Burst Peak (P): {result['P']:.2f}\n"
            res_str += f"Raw Difficulty (D0): {result['D0']:.2f}\n"
            res_str += f"Predicted Survival: {result['S_hat']:.2%}\n"
            res_str += f"Predicted S Rank (OD8): {result['S_rank_prob']:.2%}\n"
            res_str += f"Estimated Level: {result['est_level']} ({result['level_label']})\n"
            if extra_msg:
                res_str += f"{extra_msg}\n"
            res_str += "-" * 30 + "\n"
            res_str += f"HP9 Max Misses: {max_misses} (approx)\n"
            res_str += "(Assuming rest are 300s)\n"
            
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
                n_poor=self.qw_pr.get()
            )
            
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
