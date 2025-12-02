import math

class OsuParser:
    def __init__(self, file_path):
        self.file_path = file_path
        self.header = {}
        self.notes = [] # List of {'time': float, 'column': int, 'type': str, 'endtime': float}
        self.duration = 0.0
        self.key_count = 4 # Default
        
    def parse(self):
        with open(self.file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            
        section = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            if line.startswith('[') and line.endswith(']'):
                section = line[1:-1]
                continue
                
            if section == 'General':
                if ':' in line:
                    key, val = line.split(':', 1)
                    self.header[key.strip()] = val.strip()
                    
            elif section == 'Difficulty':
                if ':' in line:
                    key, val = line.split(':', 1)
                    key = key.strip()
                    val = val.strip()
                    if key == 'CircleSize':
                        self.key_count = int(float(val))
                    elif key == 'HPDrainRate':
                        self.header['HPDrainRate'] = float(val)
                    elif key == 'OverallDifficulty':
                        self.header['OverallDifficulty'] = float(val)

            elif section == 'Metadata':
                if ':' in line:
                    key, val = line.split(':', 1)
                    self.header[key.strip()] = val.strip()
                        
            elif section == 'HitObjects':
                # x,y,time,type,hitSound,objectParams,hitSample
                parts = line.split(',')
                if len(parts) < 4:
                    continue
                    
                x = int(parts[0])
                y = int(parts[1])
                time_ms = int(parts[2])
                type_flags = int(parts[3])
                
                # Calculate Column
                # Column = floor(x * KeyCount / 512)
                # Clamp x to 0-512 just in case
                x = max(0, min(512, x))
                column = int(math.floor(x * self.key_count / 512.0))
                # Osu columns are 0-indexed. Our system uses 1-indexed for some reason in BMS parser?
                # BMS Parser used: 1-7 for 1P, 8-15 for 2P.
                # Let's map Osu columns to 1-based index to match BMS parser output format.
                column += 1 
                
                # Check Type
                # Bit 0 (1): Circle
                # Bit 1 (2): Slider (not used in mania usually, but treated as LN if present?)
                # Bit 3 (8): Spinner (not used in mania)
                # Bit 7 (128): Mania Hold Note
                
                is_ln = (type_flags & 128) > 0
                
                if is_ln:
                    # For Hold Notes, end time is in extras
                    # x,y,time,type,hitSound,endTime:hitSample
                    if len(parts) > 5:
                        end_part = parts[5]
                        if ':' in end_part:
                            end_time_ms = int(end_part.split(':')[0])
                        else:
                            end_time_ms = int(end_part)
                        end_time = end_time_ms / 1000.0
                    else:
                        end_time = time_ms / 1000.0
                    
                    # BMS Style: Emit Start and End markers
                    self.notes.append({
                        'time': time_ms / 1000.0,
                        'column': column,
                        'type': 'ln_marker',
                        'value': '00'
                    })
                    self.notes.append({
                        'time': end_time,
                        'column': column,
                        'type': 'ln_marker',
                        'value': '00'
                    })
                else:
                    # Normal Note
                    self.notes.append({
                        'time': time_ms / 1000.0,
                        'column': column,
                        'type': 'note',
                        'value': '00'
                    })
                
        # Sort notes by time
        self.notes.sort(key=lambda x: x['time'])
        
        # Post-process LNs (BMS Style Pairing)
        final_notes = []
        active_lns = {} # col -> start_note
        
        for note in self.notes:
            col = note['column']
            if note['type'] == 'ln_marker':
                if col in active_lns:
                    # End of LN
                    start_note = active_lns.pop(col)
                    # Ensure duration > 0
                    if note['time'] > start_note['time']:
                        final_notes.append({
                            'time': start_note['time'],
                            'endtime': note['time'],
                            'column': col,
                            'type': 'ln'
                        })
                    else:
                        # Zero duration LN -> Treat as Normal Note?
                        # Or just ignore the end marker and keep it as note?
                        # Let's treat start as normal note
                        final_notes.append({
                            'time': start_note['time'],
                            'column': col,
                            'type': 'note'
                        })
                else:
                    # Start of LN
                    active_lns[col] = note
            else:
                # Normal note
                final_notes.append(note)
        
        # Handle open LNs (Start without End) -> Treat as Normal Note
        for col, note in active_lns.items():
            final_notes.append({
                'time': note['time'],
                'column': col,
                'type': 'note'
            })
            
        self.notes = sorted(final_notes, key=lambda x: x['time'])
        
        if self.notes:
            last_note = self.notes[-1]
            if last_note['type'] == 'ln':
                self.duration = last_note['endtime']
            else:
                self.duration = last_note['time']
        
        return self.notes

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        parser = OsuParser(sys.argv[1])
        notes = parser.parse()
        print(f"Parsed {len(notes)} notes. KeyCount: {parser.key_count}")
        for n in notes[:5]:
            print(n)
