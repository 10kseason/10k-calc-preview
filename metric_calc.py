import numpy as np

def calculate_metrics(notes, duration, window_size=1.0):
    """
    Calculate difficulty metrics for each time window.
    
    Args:
        notes: List of dicts {'time': float, 'column': int, 'type': str, 'endtime': float (optional)}
        duration: Total duration of the song in seconds
        window_size: Size of each window in seconds
        
    Returns:
        dict of numpy arrays: {
            'nps': [],
            'ln_strain': [],
            'jack_pen': [],
            'roll_pen': [],
            'alt_cost': []
        }
    """
    num_windows = int(np.ceil(duration / window_size))
    
    nps = np.zeros(num_windows)
    ln_strain = np.zeros(num_windows)
    jack_pen = np.zeros(num_windows)
    roll_pen = np.zeros(num_windows)
    alt_cost = np.zeros(num_windows)
    hand_strain = np.zeros(num_windows)
    
    # Pre-process notes into windows for faster access
    windows = [[] for _ in range(num_windows)]
    for note in notes:
        t = note['time']
        w_idx = int(t / window_size)
        if 0 <= w_idx < num_windows:
            windows[w_idx].append(note)
            
    # Calculate metrics per window
    for i in range(num_windows):
        window_notes = windows[i]
        start_time = i * window_size
        end_time = (i + 1) * window_size
        
        # 1. NPS (Notes Per Second) -> Action NPS (Chords = 1 Action)
        # Count unique timestamps in this window
        unique_times = set(n['time'] for n in window_notes)
        count = len(unique_times)
        
        # Optional: Slight bonus for chord size?
        # For now, pure Action NPS is safer for 10K Piano charts.
        nps[i] = count / window_size
        
    # Spike Dampening: Reduce impact of extreme outliers
    # Calculate stats on non-zero NPS to avoid skewing by silence
    non_zero_nps = nps[nps > 0]
    if len(non_zero_nps) > 0:
        mean_nps = np.mean(non_zero_nps)
        std_nps = np.std(non_zero_nps)
        threshold = mean_nps + 3.0 * std_nps
        
        # Apply dampening to values above threshold
        # New = Threshold + (Old - Threshold) * 0.5
        mask = nps > threshold
        nps[mask] = threshold + (nps[mask] - threshold) * 0.5
        
        # 2. LN Strain
        # Sum of active LN duration in this window
        # We need to check all notes that overlap this window, not just start in it.
        # But for efficiency, let's just use the ones starting or we need a better approach.
        # A simple approximation: sum of lengths of LNs starting in this window.
        # Better: Iterate all notes and check overlap? Too slow.
        # Let's stick to "LNs active in this window".
        # For now, simple version: Sum of (LN duration clamped to window)
        ln_sum = 0.0
        # We need to look at previous windows for LNs that extend into this one.
        # This is complex. Let's simplify:
        # LN Strain = Proportion of window occupied by LNs (sum across columns)
        # If 7 keys are held down, strain is 7.0?
        
        # Let's iterate notes again for LN calculation properly?
        # Or just use the notes in this window and assume short LNs?
        # Let's do a proper overlap check for LNs.
        # But we only have `windows` which contains starts.
        # We can maintain "active LNs" state as we iterate windows.
        pass 

    # Re-iterate for LN Strain with state
    active_lns = [] # List of (endtime, column)
    for i in range(num_windows):
        window_start = i * window_size
        window_end = (i + 1) * window_size
        
        # Add new LNs from this window
        for note in windows[i]:
            if note.get('type') == 'ln':
                active_lns.append((note['endtime'], note['column']))
        
        # Remove finished LNs
        active_lns = [ln for ln in active_lns if ln[0] > window_start]
        
        # Calculate overlap for each active LN with current window
        total_overlap = 0.0
        for end_t, col in active_lns:
            # LN start is implicitly before or in this window
            # We don't have start time here easily, but we know it started before window_end.
            # Overlap start = max(window_start, ln_start) -> We lost ln_start.
            # Actually, we should store start time too.
            pass
            
    # Let's restart LN logic.
    # We will just iterate all notes and add their contribution to relevant windows.
    ln_strain_accum = np.zeros(num_windows)
    
    for note in notes:
        if note.get('type') == 'ln':
            start = note['time']
            end = note['endtime']
            
            start_idx = int(start / window_size)
            end_idx = int(end / window_size)
            
            for w in range(start_idx, min(end_idx + 1, num_windows)):
                w_start = w * window_size
                w_end = (w + 1) * window_size
                
                overlap_start = max(start, w_start)
                overlap_end = min(end, w_end)
                overlap = max(0.0, overlap_end - overlap_start)
                
                ln_strain_accum[w] += overlap
                
    ln_strain = ln_strain_accum / window_size # Normalize to average keys held
    
    # 3. Jack Penalty
    # High if same column is hit rapidly.
    # For each window, find min interval between same-column notes.
    for i in range(num_windows):
        w_notes = windows[i]
        if not w_notes: continue
        
        col_last_time = {}
        min_diff = 1.0 # Max cap
        
        # Sort by time
        w_notes.sort(key=lambda x: x['time'])
        
        for note in w_notes:
            col = note['column']
            t = note['time']
            if col in col_last_time:
                diff = t - col_last_time[col]
                if diff < min_diff:
                    min_diff = diff
            col_last_time[col] = t
            
        # Penalty is inverse of min_diff?
        # If 100ms jack -> 10 notes/sec equivalent.
        # Let's define penalty as 1/min_diff (capped).
        if min_diff < 0.001: min_diff = 0.001
        jack_pen[i] = 1.0 / min_diff if min_diff < 0.2 else 0.0 # Only penalize if faster than 200ms (5 NPS)
        
    # 4. Roll Penalty
    # Tricky to detect generic rolls.
    # Let's approximate: High NPS but low Jack Penalty?
    # Or specific patterns.
    # Simple heuristic: Variance of columns used?
    # If using 1-2-1-2, variance is low (only 2 cols).
    # If using 1-2-3-4-5-6-7, variance is high.
    # Actually, rolls are usually 2-4 keys repeated.
    # Let's skip complex pattern detection and use "Density of notes" vs "Unique columns".
    # Roll Penalty = (NPS) / (Unique Columns + 1) * Factor?
    # No, that's vague.
    # Let's leave Roll Penalty as 0 for now or simple placeholder.
    # Placeholder: 10% of NPS if Jack is low.
    roll_pen = nps * 0.1 
    
    # 5. Alt Cost & Hand Strain (Action-based)
    # Instead of counting notes, we count "actions" (unique timestamps) per hand.
    
    max_col = 0
    for note in notes:
        max_col = max(max_col, note['column'])
    is_dp = max_col > 7

    for i in range(num_windows):
        w_notes = windows[i]
        
        l_timestamps = set()
        r_timestamps = set()
        
        if is_dp:
            # DP Mode: 1P Side (0-7) vs 2P Side (8-15)
            for note in w_notes:
                c = note['column']
                t = note['time']
                if c <= 7: l_timestamps.add(t)
                else: r_timestamps.add(t)
        else:
            # SP Mode: Left (1,2,3) vs Right (5,6,7)
            for note in w_notes:
                c = note['column']
                t = note['time']
                if c in [0, 1, 2, 3]: l_timestamps.add(t)
                elif c in [5, 6, 7]: r_timestamps.add(t)
                elif c == 4: 
                    if len(l_timestamps) <= len(r_timestamps):
                        l_timestamps.add(t)
                    else:
                        r_timestamps.add(t)
            
        l_actions = len(l_timestamps)
        r_actions = len(r_timestamps)
        
        diff = abs(l_actions - r_actions)
        alt_cost[i] = diff / window_size
        
        # Hand Strain: Max Actions Per Second of either hand
        hand_strain[i] = max(l_actions, r_actions) / window_size
        
    return {
        'nps': nps,
        'ln_strain': ln_strain,
        'jack_pen': jack_pen,
        'roll_pen': roll_pen,
        'alt_cost': alt_cost,
        'hand_strain': hand_strain
    }
