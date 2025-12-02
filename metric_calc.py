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
    chord_strain = np.zeros(num_windows)
    
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
    # 3. Jack Penalty
    # High if same column is hit rapidly.
    # [Modified] "Jack Nerf should only apply to Code Jacks"
    # Strategy: Calculate Jack Score for each event.
    # If it's a "Code Jack" (Same Chord Repeated), apply a nerf factor (e.g. 0.5).
    # Take the MAX score in the window.
    
    for i in range(num_windows):
        w_notes = windows[i]
        if not w_notes: continue
        
        # Build time_to_cols for Code Jack detection
        time_to_cols = {}
        for note in w_notes:
            t = note['time']
            if t not in time_to_cols:
                time_to_cols[t] = set()
            time_to_cols[t].add(note['column'])
            
        col_last_time = {}
        max_jack_score = 0.0
        
        # Sort by time
        w_notes.sort(key=lambda x: x['time'])
        
        for note in w_notes:
            col = note['column']
            t = note['time']
            
            if col in col_last_time:
                diff = t - col_last_time[col]
                if diff < 0.001: diff = 0.001
                
                # Calculate Raw Score
                # Capped Linear Mapping: 0.2s -> 0, 0.0s -> 25.0
                if diff < 0.2:
                    raw_score = 25.0 * (0.2 - diff) / 0.2
                    
                    # Check for Code Jack
                    # Same Key Combination Repeated?
                    prev_t = col_last_time[col]
                    cols_curr = time_to_cols.get(t, set())
                    cols_prev = time_to_cols.get(prev_t, set())
                    
                    is_code_jack = False
                    if len(cols_curr) > 1 and cols_curr == cols_prev:
                        is_code_jack = True
                        
                    if is_code_jack:
                        # Apply Nerf
                        raw_score *= 0.5
                        
                    if raw_score > max_jack_score:
                        max_jack_score = raw_score
                        
            col_last_time[col] = t
            
        jack_pen[i] = max_jack_score

    # 4. Roll Penalty (Variance based)
    for i in range(num_windows):
        w_notes = windows[i]
        if len(w_notes) > 1:
            cols = [n['column'] for n in w_notes]
            col_var = np.var(cols)
            roll_pen[i] = col_var * nps[i] * 0.1
        else:
            roll_pen[i] = 0.0

    # 5. Alt Cost & Hand Strain
    max_col = 0
    if notes:
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
        
        hand_strain[i] = max(l_actions, r_actions) / window_size
        
        # 6. Chord Strain
        chord_strain_val = 0.0
        time_counts = {}
        for note in w_notes:
            t = note['time']
            time_counts[t] = time_counts.get(t, 0) + 1
            
        for t, count in time_counts.items():
            if count > 1:
                # [수정] Log scaling for chord strain (User Feedback)
                # log1p(count) applied to each chord? Or log1p(total)?
                # User said: "chord_strain[i] = np.log1p(chord_strain_val)"
                # So we sum first, then log.
                chord_strain_val += (count - 1)
                
        chord_strain[i] = np.log1p(chord_strain_val)

    return {
        'nps': nps,
        'ln_strain': ln_strain,
        'jack_pen': jack_pen,
        'roll_pen': roll_pen,
        'alt_cost': alt_cost,
        'hand_strain': hand_strain,
        'chord_strain': chord_strain
    }
