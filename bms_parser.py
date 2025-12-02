import re
import math

class BMSParser:
    def __init__(self, file_path):
        self.file_path = file_path
        self.header = {}
        self.bms_data = []  # List of (measure, channel, value)
        self.bpm_definitions = {}
        self.stop_definitions = {}
        self.notes = [] # List of {'time': float, 'column': int, 'type': str}
        self.duration = 0.0
        
        # Channel Mappings for 7Key (1P)
        self.channel_map = {
            '11': 1, '12': 2, '13': 3, '14': 4, '15': 5, '18': 6, '19': 7, '16': 0, # 0 for Scratch
            # Long Notes
            '51': 1, '52': 2, '53': 3, '54': 4, '55': 5, '58': 6, '59': 7, '56': 0,
            # 2P Channels (DP)
            '21': 8, '22': 9, '23': 10, '24': 11, '25': 12, '28': 13, '29': 14, '26': 15, # 15 for 2P Scratch
            # 2P Long Notes
            '61': 8, '62': 9, '63': 10, '64': 11, '65': 12, '68': 13, '69': 14, '66': 15
        }
        
    def parse(self):
        with open(self.file_path, 'r', encoding='shift_jis', errors='ignore') as f:
            lines = f.readlines()
            
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            if line.startswith('#'):
                # Check for Channel Data #XXXYY:DATA
                if ':' in line:
                    parts = line[1:].split(':', 1)
                    key_part = parts[0]
                    data_part = parts[1]
                    
                    if len(key_part) == 5 and key_part.isdigit():
                        measure = int(key_part[0:3])
                        channel = key_part[3:5]
                        self.bms_data.append((measure, channel, data_part))
                        continue
                
                # Header Data #KEY VALUE
                parts = line[1:].split(' ', 1)
                key = parts[0]
                value = parts[1] if len(parts) > 1 else ""
                
                if key.startswith('BPM') and len(key) == 5:
                    # #BPMxx n
                    bpm_id = key[3:5]
                    try:
                        self.bpm_definitions[bpm_id] = float(value)
                    except ValueError:
                        pass
                elif key == 'BPM':
                    try:
                        self.header['BPM'] = float(value)
                    except ValueError:
                        self.header['BPM'] = 130.0 # Default
                elif key == 'STOP':
                    # #STOPxx n
                    if len(key) > 4:
                         stop_id = key[4:6] # Wait, #STOPxx
                         # Actually usually #STOPxx n
                         pass
                elif key.startswith('STOP') and len(key) == 6:
                     stop_id = key[4:6]
                     try:
                         self.stop_definitions[stop_id] = float(value)
                     except ValueError:
                         pass
                elif key == 'TOTAL':
                    try:
                        self.header['TOTAL'] = float(value)
                    except ValueError:
                        pass
                else:
                    self.header[key] = value

        self._process_data()
        return self.notes

    def _process_data(self):
        # Sort data by measure
        self.bms_data.sort(key=lambda x: x[0])
        
        # Time Calculation Variables
        current_bpm = self.header.get('BPM', 130.0)
        seconds_per_beat = 60.0 / current_bpm
        current_time = 0.0
        
        # We need to process measures sequentially to track time
        # Group by measure
        measure_data = {}
        max_measure = 0
        for m, c, d in self.bms_data:
            if m not in measure_data:
                measure_data[m] = []
            measure_data[m].append((c, d))
            max_measure = max(max_measure, m)
            
        # Measure Lengths (default 1.0 = 4/4)
        measure_lengths = {}
        for m in range(max_measure + 1):
             measure_lengths[m] = 1.0
             
        # Check for #XXX02 (Measure Length Change)
        for m, c, d in self.bms_data:
            if c == '02':
                try:
                    measure_lengths[m] = float(d)
                except ValueError:
                    pass

        # Process Measures
        for m in range(max_measure + 1):
            length_ratio = measure_lengths.get(m, 1.0)
            beats_in_measure = 4.0 * length_ratio
            
            # Events in this measure need to be sorted by position
            events = []
            
            if m in measure_data:
                for channel, data_str in measure_data[m]:
                    total_objects = len(data_str) // 2
                    for i in range(total_objects):
                        obj_val = data_str[i*2 : i*2+2]
                        if obj_val == '00':
                            continue
                        
                        position = i / total_objects # 0.0 to 1.0 within measure
                        events.append({
                            'position': position,
                            'channel': channel,
                            'value': obj_val,
                            'beat_offset': position * beats_in_measure
                        })
            
            # Sort events by position
            events.sort(key=lambda x: x['position'])
            
            # Iterate through events and advance time
            # But wait, multiple events can happen at the same time (chords)
            # And BPM changes affect time calculation between events.
            
            # We can't just iterate events because BPM changes might happen at position 0.5
            # and a note might be at 0.7.
            # So we need to process time strictly.
            
            # Let's collect all "time-points" in this measure where something happens
            time_points = set()
            time_points.add(0.0)
            time_points.add(1.0) # End of measure
            for e in events:
                time_points.add(e['position'])
            
            sorted_points = sorted(list(time_points))
            
            # Calculate time for each segment
            measure_start_time = current_time
            
            # Map position -> time
            pos_to_time = {}
            
            last_pos = 0.0
            for pos in sorted_points:
                if pos == 0.0:
                    pos_to_time[0.0] = current_time
                    continue
                
                # Calculate duration from last_pos to pos
                beats_delta = (pos - last_pos) * beats_in_measure
                duration = beats_delta * (60.0 / current_bpm)
                current_time += duration
                pos_to_time[pos] = current_time
                
                # Check for events at this exact position (specifically BPM changes)
                # We need to process BPM changes that happened AT last_pos before calculating duration to next?
                # Actually, BPM change at position X applies to the segment starting at X.
                
                # So we need to check events at `last_pos` to update BPM for the NEXT segment.
                # But we just calculated the segment ending at `pos`.
                # So we should have updated BPM at `last_pos`.
                
                # Let's refine this loop.
                pass

            # Refined Time Loop
            # Reset current_time to measure_start
            current_time = measure_start_time
            last_pos = 0.0
            
            # Group events by position
            events_by_pos = {}
            for e in events:
                p = e['position']
                if p not in events_by_pos: events_by_pos[p] = []
                events_by_pos[p].append(e)
                
            for pos in sorted_points:
                if pos > last_pos:
                    beats_delta = (pos - last_pos) * beats_in_measure
                    duration = beats_delta * (60.0 / current_bpm)
                    current_time += duration
                
                # Process events at this position
                if pos in events_by_pos:
                    for e in events_by_pos[pos]:
                        ch = e['channel']
                        val = e['value']
                        
                        # BPM Change (Standard)
                        if ch == '03':
                            try:
                                current_bpm = float(int(val, 16))
                            except: pass
                        # BPM Change (Extended)
                        elif ch == '08':
                            if val in self.bpm_definitions:
                                current_bpm = self.bpm_definitions[val]
                        
                        # Check LNOBJ
                        ln_obj = self.header.get('LNOBJ')
                        
                        # Note Object
                        if ch in self.channel_map:
                            key_num = self.channel_map[ch]
                            is_ln_channel = ch.startswith('5') or ch.startswith('6') # 5x, 6x are always LN
                            
                            # LNOBJ Logic: If value matches LNOBJ, it's an LN End marker
                            is_ln_obj = (ln_obj and val.upper() == ln_obj.upper())
                            
                            if is_ln_obj:
                                # This is an LN End marker.
                                # We treat it as an 'ln_marker' type, but specifically for LNOBJ pairing.
                                # Actually, standard LN logic uses pairs.
                                # If we mark this as 'ln_marker', the post-processor needs to know.
                                # Let's use a specific type or just rely on pairing?
                                # If we use 'ln_marker', we need to ensure the START was also an 'ln_marker'.
                                # But the start was likely parsed as a 'note' because we didn't know yet.
                                # So we need to handle this in post-processing or here.
                                
                                # Better approach: Mark it as 'ln_end'
                                self.notes.append({
                                    'time': current_time,
                                    'column': key_num,
                                    'type': 'ln_end',
                                    'value': val
                                })
                            else:
                                self.notes.append({
                                    'time': current_time,
                                    'column': key_num,
                                    'type': 'ln' if is_ln_channel else 'note',
                                    'value': val
                                })
                            
                last_pos = pos
            
            # End of measure loop
            pass
        
        self.duration = current_time
        
        # Post-process LNs
        self.notes.sort(key=lambda x: x['time'])
        
        final_notes = []
        active_lns = {} # col -> start_note
        
        for note in self.notes:
            col = note['column']
            n_type = note['type']
            
            if n_type == 'ln':
                # Standard LN Channel (5x/6x) or LNTYPE 1 Pair
                if col in active_lns:
                    start_note = active_lns.pop(col)
                    final_notes.append({
                        'time': start_note['time'],
                        'endtime': note['time'],
                        'column': col,
                        'type': 'ln'
                    })
                else:
                    active_lns[col] = note
            
            elif n_type == 'ln_end':
                # LNOBJ End Marker
                # Pairs with the most recent 'note' on this column
                # We need to find the last note added to final_notes for this column?
                # Or maybe we should have kept it in a buffer?
                
                # Since we are iterating sorted notes, the start note must be in final_notes (as a 'note')
                # or in active_lns (if we treated it as LN start, but we treated it as 'note').
                
                # We need to look backwards in final_notes to find the start.
                # This is inefficient.
                # Alternative: When we see 'ln_end', we convert the LAST 'note' on this column into 'ln'.
                
                # Let's track last_seen_note per column
                found_start = False
                # Iterate backwards through final_notes to find the last 'note' on this col
                for i in range(len(final_notes)-1, -1, -1):
                    cand = final_notes[i]
                    if cand['column'] == col and cand['type'] == 'note':
                        # Found it! Convert to LN
                        cand['type'] = 'ln'
                        cand['endtime'] = note['time']
                        found_start = True
                        break
                
                if not found_start:
                    # Orphan End? Ignore or treat as note?
                    # LNOBJ end marker itself is usually not a note if it's just a marker.
                    # But if it fails to pair, maybe it should be a note?
                    # Usually LNOBJ is just a marker.
                    pass
                    
            else:
                # Normal Note
                final_notes.append(note)
        
        # Handle open LNs from 5x/6x
        for col, note in active_lns.items():
            note['type'] = 'note'
            final_notes.append(note)
            
        self.notes = sorted(final_notes, key=lambda x: x['time'])

if __name__ == "__main__":
    # Test
    import sys
    if len(sys.argv) > 1:
        parser = BMSParser(sys.argv[1])
        notes = parser.parse()
        print(f"Parsed {len(notes)} notes.")
        for n in notes[:10]:
            print(n)
