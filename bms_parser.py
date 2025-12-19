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
        self.key_count = 8  # 기본값: 8키 (7+1), 키 모드 감지 후 변경됨
        self.play_mode = 'SP'  # 'SP' (Single Play) 또는 'DP' (Double Play)
        self.detected_mode = None  # 감지된 키 모드 이름 (예: '7+1', '10K', 'DP14')
        
        # ============================================================
        # 키 모드별 채널 패턴 정의
        # 키: (채널 세트, 키 개수, 모드 이름)
        # 채널 세트: frozenset of 사용 채널 (일반 노트만, LN은 +40)
        # ============================================================
        self.key_mode_patterns = [
            # DP/대형 모드 (먼저 체크 - 2P 채널 포함)
            # 16키: 16 11-15 18-19 21-25 28-29 26 (스크 포함)
            ({'16', '11', '12', '13', '14', '15', '18', '19', '21', '22', '23', '24', '25', '28', '29', '26'}, 16, 'DP16'),
            # 14키: 11-15 18-19 21-25 28-29 (스크 없음)
            ({'11', '12', '13', '14', '15', '18', '19', '21', '22', '23', '24', '25', '28', '29'}, 14, 'DP14'),
            # 12키: 16 11-15 21-25 26 (스크 포함)
            ({'16', '11', '12', '13', '14', '15', '21', '22', '23', '24', '25', '26'}, 12, 'DP12'),
            # 10키: 11-15 21-25 (스크 없음)
            ({'11', '12', '13', '14', '15', '21', '22', '23', '24', '25'}, 10, '10K'),
            # 9키 PMS: 11-15 22-25
            ({'11', '12', '13', '14', '15', '22', '23', '24', '25'}, 9, '9K_PMS'),
            
            # SP 모드 (1P만)
            # 8키 (7+1): 16 11-15 18-19
            ({'16', '11', '12', '13', '14', '15', '18', '19'}, 8, '7+1'),
            # 7키: 11-15 18-19 (스크 없음)
            ({'11', '12', '13', '14', '15', '18', '19'}, 7, '7K'),
            # 6키 (#6K): 11 12 13 15 18 19
            ({'11', '12', '13', '15', '18', '19'}, 6, '6K'),
            # 6키 (5+1): 16 11-15
            ({'16', '11', '12', '13', '14', '15'}, 6, '5+1'),
            # 5키: 11-15 (스크 없음)
            ({'11', '12', '13', '14', '15'}, 5, '5K'),
            # 4키: 11 12 14 15
            ({'11', '12', '14', '15'}, 4, '4K'),
        ]
        
        # ============================================================
        # 키 모드별 채널 → 열 매핑
        # 키: 모드 이름, 값: {채널: 열} 딕셔너리
        # 열 번호는 1-indexed (OSU 호환)
        # ============================================================
        self.key_mode_mappings = {
            # 16키 DP: SC(16) 1-7(11-15,18-19) | 1-7(21-25,28-29) SC(26)
            'DP16': {
                '16': 1, '11': 2, '12': 3, '13': 4, '14': 5, '15': 6, '18': 7, '19': 8,
                '21': 9, '22': 10, '23': 11, '24': 12, '25': 13, '28': 14, '29': 15, '26': 16,
            },
            # 14키 DP: 1-7(11-15,18-19) | 1-7(21-25,28-29) - 스크 없음
            'DP14': {
                '11': 1, '12': 2, '13': 3, '14': 4, '15': 5, '18': 6, '19': 7,
                '21': 8, '22': 9, '23': 10, '24': 11, '25': 12, '28': 13, '29': 14,
            },
            # 12키 DP: SC(16) 1-5(11-15) | 1-5(21-25) SC(26)
            'DP12': {
                '16': 1, '11': 2, '12': 3, '13': 4, '14': 5, '15': 6,
                '21': 7, '22': 8, '23': 9, '24': 10, '25': 11, '26': 12,
            },
            # 10키: 1-5(11-15) | 1-5(21-25) - 스크 없음
            '10K': {
                '11': 1, '12': 2, '13': 3, '14': 4, '15': 5,
                '21': 6, '22': 7, '23': 8, '24': 9, '25': 10,
            },
            # 9키 PMS: 1-5(11-15) 6-9(22-25)
            '9K_PMS': {
                '11': 1, '12': 2, '13': 3, '14': 4, '15': 5,
                '22': 6, '23': 7, '24': 8, '25': 9,
            },
            # 8키 (7+1): SC(16) 1-7(11-15,18-19)
            '7+1': {
                '16': 1, '11': 2, '12': 3, '13': 4, '14': 5, '15': 6, '18': 7, '19': 8,
            },
            # 7키: 1-7(11-15,18-19) - 스크 없음
            '7K': {
                '11': 1, '12': 2, '13': 3, '14': 4, '15': 5, '18': 6, '19': 7,
            },
            # 6키 (#6K): 11 12 13 15 18 19 → 1-6
            '6K': {
                '11': 1, '12': 2, '13': 3, '15': 4, '18': 5, '19': 6,
            },
            # 6키 (5+1): SC(16) 1-5(11-15)
            '5+1': {
                '16': 1, '11': 2, '12': 3, '13': 4, '14': 5, '15': 6,
            },
            # 5키: 1-5(11-15) - 스크 없음
            '5K': {
                '11': 1, '12': 2, '13': 3, '14': 4, '15': 5,
            },
            # 4키: 11 12 14 15 → 1-4
            '4K': {
                '11': 1, '12': 2, '14': 3, '15': 4,
            },
        }
        
        # Fallback: 기존 매핑 (감지 실패 시 사용)
        self.channel_map_fallback = {
            # 1P Channels (11-19)
            '11': 1, '12': 2, '13': 3, '14': 4, '15': 5, '16': 0, '17': 8, '18': 6, '19': 7,
            # 1P Long Notes (51-59)
            '51': 1, '52': 2, '53': 3, '54': 4, '55': 5, '56': 0, '57': 8, '58': 6, '59': 7,
            # 2P Channels (21-29)
            '21': 9, '22': 10, '23': 11, '24': 12, '25': 13, '26': 16, '28': 14, '29': 15,
            # 2P Long Notes (61-69)
            '61': 9, '62': 10, '63': 11, '64': 12, '65': 13, '66': 16, '68': 14, '69': 15
        }
        
        # 현재 사용할 채널 맵 (키 모드 감지 후 설정됨)
        self.channel_map = {}
        
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
        
        # ============================================================
        # 키 모드 감지 (노트 처리 전에 채널 맵 설정)
        # ============================================================
        self._detect_key_mode()
        
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
                                    'time': round(current_time, 3),  # ms 단위로 반올림
                                    'column': key_num,
                                    'type': 'ln_end',
                                    'value': val
                                })
                            else:
                                self.notes.append({
                                    'time': round(current_time, 3),  # ms 단위로 반올림
                                    'column': key_num,
                                    'type': 'ln' if is_ln_channel else 'note',
                                    'value': val
                                })
                            
                last_pos = pos
            
            # End of measure loop
            pass
        
        self.duration = current_time
        
        # Post-process LNs - Count LN as 2 notes (start + end) like Osu
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
                    # Add START note
                    final_notes.append({
                        'time': start_note['time'],
                        'column': col,
                        'type': 'ln_start'
                    })
                    # Add END note (counts as separate note for NPS)
                    final_notes.append({
                        'time': note['time'],
                        'column': col,
                        'type': 'ln_end'
                    })
                else:
                    active_lns[col] = note
            
            elif n_type == 'ln_end':
                # LNOBJ End Marker
                found_start = False
                for i in range(len(final_notes)-1, -1, -1):
                    cand = final_notes[i]
                    if cand['column'] == col and cand['type'] == 'note':
                        # Convert to LN start + add LN end
                        cand['type'] = 'ln_start'
                        final_notes.append({
                            'time': note['time'],
                            'column': col,
                            'type': 'ln_end'
                        })
                        found_start = True
                        break
                
                if not found_start:
                    pass
                    
            else:
                # Normal Note
                final_notes.append(note)
        
        # Handle open LNs from 5x/6x - treat as single note
        for col, note in active_lns.items():
            note['type'] = 'note'
            final_notes.append(note)
            
        self.notes = sorted(final_notes, key=lambda x: x['time'])
        
        # Duration = last note time - first note time
        if self.notes:
            first_time = self.notes[0]['time']
            last_time = self.notes[-1]['time']
            self.duration = last_time - first_time
            if self.duration < 1.0:  # Minimum 1 second
                self.duration = 1.0
        
        # ============================================================
        # 키 모드 감지 (열 재매핑은 이미 파싱 시 적용됨)
        # ============================================================
        # 키 모드는 이미 _detect_key_mode에서 설정됨
        # 여기서는 추가 검증만 수행
        if self.detected_mode:
            # DP 모드 판별
            if self.detected_mode.startswith('DP') or self.detected_mode in ['10K', '9K_PMS']:
                self.play_mode = 'DP'
            else:
                self.play_mode = 'SP'
    
    def _detect_key_mode(self):
        """
        BMS 데이터에서 사용된 채널을 분석하여 키 모드를 감지하고
        적절한 채널 → 열 매핑을 설정합니다.
        
        이 메서드는 _process_data 시작 시 호출되어야 합니다.
        """
        # 사용된 노트 채널 수집 (11-19, 21-29, 51-59, 61-69)
        used_note_channels = set()
        
        for measure, channel, data in self.bms_data:
            # 노트 채널인지 확인 (1x, 2x, 5x, 6x)
            if channel.startswith('1') or channel.startswith('2') or \
               channel.startswith('5') or channel.startswith('6'):
                # 데이터가 비어있지 않은지 확인
                total_objects = len(data) // 2
                has_notes = any(data[i*2:i*2+2] != '00' for i in range(total_objects))
                if has_notes:
                    # LN 채널(5x, 6x)은 일반 채널(1x, 2x)로 변환하여 분석
                    if channel.startswith('5'):
                        base_ch = '1' + channel[1]
                    elif channel.startswith('6'):
                        base_ch = '2' + channel[1]
                    else:
                        base_ch = channel
                    used_note_channels.add(base_ch)
        
        # 키 모드 패턴 매칭
        # 사용된 채널을 모두 포함하는 가장 작은 패턴(키 개수가 작은 것) 선택
        best_match = None
        best_key_count = float('inf')  # 가장 작은 것 우선
        
        for pattern_channels, key_count, mode_name in self.key_mode_patterns:
            # 사용된 채널이 패턴의 부분집합인지 확인
            if used_note_channels.issubset(pattern_channels):
                # 가장 작은 키 개수 우선 (더 정확한 매칭)
                if key_count < best_key_count:
                    best_match = mode_name
                    best_key_count = key_count
        
        # 매칭되지 않으면 사용된 채널 수로 추정
        if best_match is None:
            # 2P 채널(21-29) 사용 여부로 DP/SP 구분
            has_2p = any(ch.startswith('2') for ch in used_note_channels)
            if has_2p:
                # 사용된 채널 수로 키 모드 추정
                total_channels = len(used_note_channels)
                if total_channels >= 14:
                    best_match = 'DP16'
                    best_key_count = 16
                elif total_channels >= 10:
                    best_match = 'DP14'
                    best_key_count = 14
                else:
                    best_match = '10K'
                    best_key_count = 10
            else:
                # SP 모드: 사용된 채널 수로 키 모드 추정
                if '16' in used_note_channels:  # 스크래치 있음
                    if '18' in used_note_channels or '19' in used_note_channels:
                        best_match = '7+1'
                        best_key_count = 8
                    else:
                        best_match = '5+1'
                        best_key_count = 6
                else:  # 스크래치 없음
                    total_channels = len(used_note_channels)
                    if total_channels >= 7:
                        best_match = '7K'
                        best_key_count = 7
                    elif total_channels >= 5:
                        best_match = '5K'
                        best_key_count = 5
                    else:
                        best_match = '4K'
                        best_key_count = 4
        
        # 결과 저장
        self.detected_mode = best_match
        self.key_count = best_key_count
        
        # 채널 맵 설정
        if best_match and best_match in self.key_mode_mappings:
            base_map = self.key_mode_mappings[best_match]
            self.channel_map = base_map.copy()
            
            # LN 채널 매핑 추가 (5x → 1x와 동일, 6x → 2x와 동일)
            for ch, col in list(base_map.items()):
                if ch.startswith('1'):
                    ln_ch = '5' + ch[1]
                    self.channel_map[ln_ch] = col
                elif ch.startswith('2'):
                    ln_ch = '6' + ch[1]
                    self.channel_map[ln_ch] = col
        else:
            # Fallback 매핑 사용
            self.channel_map = self.channel_map_fallback.copy()
            self.key_count = 17 if any(ch.startswith('2') for ch in used_note_channels) else 8

if __name__ == "__main__":
    # Test
    import sys
    if len(sys.argv) > 1:
        parser = BMSParser(sys.argv[1])
        notes = parser.parse()
        print(f"Play Mode: {parser.play_mode}, Key Count: {parser.key_count}")
        print(f"Parsed {len(notes)} notes.")
        for n in notes[:10]:
            print(n)
