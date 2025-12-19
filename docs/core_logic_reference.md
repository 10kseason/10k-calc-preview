# 핵심 로직 참조 문서 (Core Logic Reference)

> **⚠️ 절대 기준 문서**: 이 문서의 로직은 수정하지 않고 유지해야 합니다.  
> 마지막 업데이트: 2025-12-10 (부동소수점 오차 방지 추가)

---

## 목차
1. [BMS 파서 (bms_parser.py)](#1-bms-파서)
2. [OSU 파서 (osu_parser.py)](#2-osu-파서)
3. [선형 계산 모델 (new_calc.py)](#3-선형-계산-모델)
4. [NPS 계산 표준](#4-nps-계산-표준)
5. [노트 타입 정의](#5-노트-타입-정의)
6. [메트릭 계산 (metric_calc.py)](#6-메트릭-계산)
7. [그래프 출력 (main_gui.py)](#7-그래프-출력)

---

## 1. BMS 파서

### 1.1 키 모드 자동 감지

BMS 파서는 사용된 채널을 분석하여 키 모드를 자동 감지합니다.

| 모드 | 키 개수 | 사용 채널 | 설명 |
|------|--------|----------|------|
| 4K | 4 | 11 12 14 15 | #6K 선언 시 |
| 5K | 5 | 11-15 | 스크래치 없음 |
| 5+1 | 6 | 16 11-15 | 스크래치 포함 |
| 6K | 6 | 11 12 13 15 18 19 | #6K |
| 7K | 7 | 11-15 18 19 | 스크래치 없음 |
| 7+1 | 8 | 16 11-15 18 19 | 스크래치 포함 |
| 9K_PMS | 9 | 11-15 22-25 | PMS 파일 |
| 10K | 10 | 11-15 21-25 | 스크래치 없음 |
| DP12 | 12 | 16 11-15 21-25 26 | 스크래치 포함 |
| DP14 | 14 | 11-15 18-19 21-25 28-29 | 스크래치 없음 |
| DP16 | 16 | 16 11-15 18-19 21-25 28-29 26 | 스크래치 포함 |

**감지 로직**: `_detect_key_mode()` 메서드에서 노트가 있는 채널을 수집하고, 가장 작은 superset 패턴을 선택.

### 1.2 키 모드별 열(Column) 매핑

모든 키 모드에서 열은 **1-indexed** (1부터 시작).

```python
# 예시: 10K 매핑
'10K': {
    '11': 1, '12': 2, '13': 3, '14': 4, '15': 5,
    '21': 6, '22': 7, '23': 8, '24': 9, '25': 10,
}

# 예시: DP12 매핑
'DP12': {
    '16': 1, '11': 2, '12': 3, '13': 4, '14': 5, '15': 6,
    '21': 7, '22': 8, '23': 9, '24': 10, '25': 11, '26': 12,
}
```

**LN 채널**: 5x/6x 채널은 자동으로 1x/2x와 동일한 열로 매핑됨.

### 1.3 롱노트 처리

| LN 방식 | 채널 | 처리 방법 |
|---------|------|----------|
| 표준 LN | 5x/6x | 첫 오브젝트 = ln_start, 두 번째 = ln_end |
| LNOBJ | #LNOBJ xx | 헤더에 정의된 값이면 ln_end |
| LNTYPE 1 | 1x/2x 페어링 | 동일 열의 연속 노트를 ln_start/ln_end로 변환 |

**중요**: 롱노트는 **2개 노트로 계산** (`ln_start` + `ln_end`)

### 1.4 시간 계산

```python
# 마디 내 위치 → 시간 변환
beats_in_measure = 4.0 * length_ratio  # 기본 4/4 박자
position = object_index / total_objects  # 0.0 ~ 1.0
beat_offset = position * beats_in_measure
duration = beats_delta * (60.0 / current_bpm)

# **중요**: 모든 노트 시간은 ms 단위로 반올림
time = round(current_time, 3)  # 부동소수점 오차 방지
```

### 1.5 곡 길이 (Duration)

```python
duration = last_note_time - first_note_time
if duration < 1.0:
    duration = 1.0  # 최소 1초
```

---

## 2. OSU 파서

### 2.1 열(Column) 계산

```python
# Osu!mania 열 공식
column = floor(x * key_count / 512)
column += 1  # 1-indexed (BMS와 통일)

# **중요**: 모든 노트 시간은 ms 단위로 반올림
time = round(time_ms / 1000.0, 3)  # 부동소수점 오차 방지
```

### 2.2 노트 타입 비트 플래그

| 비트 | 값 | 의미 |
|------|-----|------|
| 0 | 1 | Circle (일반 노트) |
| 1 | 2 | Slider |
| 3 | 8 | Spinner |
| 7 | 128 | Mania Hold Note (롱노트) |

### 2.3 롱노트 처리

```python
# 롱노트 여부 확인
is_ln = (type_flags & 128) > 0

# 롱노트면 시작/끝 마커 2개 생성
if is_ln:
    notes.append({'time': start, 'column': col, 'type': 'ln_marker'})
    notes.append({'time': end, 'column': col, 'type': 'ln_marker'})
```

**중요**: OSU도 롱노트를 **2개 노트로 계산** (`ln_start` + `ln_end`)

### 2.4 키 개수 (Key Count)

```python
# [Difficulty] 섹션의 CircleSize 값
key_count = int(CircleSize)  # 4K, 7K, 10K 등
```

---

## 3. 선형 계산 모델

### 3.1 3-Feature 선형 회귀 모델

```python
# level = intercept + coef_nps*global_nps + coef_std*nps_std + coef_chord*chord_mean
NPS_LINEAR_PARAMS = {
    'intercept': -0.1879,
    'coef_nps': 0.2053,
    'coef_std': 0.9999,
    'coef_chord': 3.2741
}
```

**정확도**: BMS 1759개 기준 **MAE 1.12**

### 3.2 단순 NPS 모델 (백업)

```python
# level = 0.6963 * NPS + 1.6395
simple_params = {
    'intercept': 1.6395,
    'coef_nps': 0.6963
}
```

**정확도**: MAE 1.55

### 3.3 티어 레이블

| 레벨 범위 | 티어 |
|----------|------|
| 1-5 | 초보자 (Beginner) |
| 5-8 | 초중수 (Intermediate) |
| 8-12 | 중수 (Skilled) |
| 12-14 | 중고수 (Advanced) |
| 14-16 | 고수 (Expert) |
| 16-19 | 초고수 (Master) |
| 19-22 | Professional |
| 22+ | God |

---

## 4. NPS 계산 표준

### 4.1 Global NPS

```python
global_nps = total_notes / duration
```

- `total_notes`: 모든 노트 개수 (롱노트는 2개로 계산)
- `duration`: 첫 노트 ~ 마지막 노트 시간

### 4.2 Local NPS (Peak NPS용)

```python
# 각 노트 중심 ±500ms 구간 내 노트 개수
for note in notes:
    t = round(note['time'], 3)  # ms 단위로 반올림
    
    # 부동소수점 오차 방지: t+0.5 대신 t+0.499999999999 사용 후 <= 비교
    window_start = t - 0.5  # ±500ms
    window_end = t + 0.499999999999  # 부동소수점 오차 방지
    count = sum(1 for n in notes if window_start <= n['time'] <= window_end)
    local_nps_values.append(count)

peak_nps = max(local_nps_values)
```

**주의**: 비교 연산자 `<=` 사용 (기존 `<`에서 변경)

### 4.3 NPS 표준편차

```python
# 1초 윈도우별 NPS의 표준편차
window_nps = []
for t in range(int(duration) + 1):
    count = sum(1 for n in notes if t <= n['time'] < t + 1)
    window_nps.append(count)

nps_std = np.std(window_nps)
```

---

## 5. 노트 타입 정의

### 5.1 표준 노트 타입

| 타입 | 설명 | 노트 카운트 |
|------|------|------------|
| `note` | 일반 노트 | 1 |
| `ln_start` | 롱노트 시작 | 1 |
| `ln_end` | 롱노트 끝 | 1 |
| `ln_marker` | LN 마커 (OSU 임시) | 페어링 후 변환 |

### 5.2 LN 페어링 로직

```python
active_lns = {}  # col -> start_note

for note in notes:
    col = note['column']
    if note['type'] == 'ln_marker':
        if col in active_lns:
            # LN 끝: ln_start + ln_end 생성
            start_note = active_lns.pop(col)
            final_notes.append({'type': 'ln_start', ...})
            final_notes.append({'type': 'ln_end', ...})
        else:
            # LN 시작: 대기열에 추가
            active_lns[col] = note
```

---

## 6. 메트릭 계산 (metric_calc.py)

### 6.1 윈도우 기반 메트릭

모든 메트릭은 **1초 윈도우** 단위로 계산됩니다.

```python
num_windows = int(np.ceil(duration / window_size))  # window_size = 1.0초

# 노트를 윈도우별로 분류
windows = [[] for _ in range(num_windows)]
for note in notes:
    t = note['time']
    w_idx = int(t / window_size)
    if 0 <= w_idx < num_windows:
        windows[w_idx].append(note)
```

### 6.2 Action NPS

코드(동시치기)는 1 액션으로 계산:

```python
# 고유 타임스탬프 개수 = 액션 수
unique_times = set(n['time'] for n in window_notes)
nps[i] = len(unique_times) / window_size
```

### 6.3 Spike Dampening

극단적 NPS 스파이크 완화:

```python
threshold = mean_nps + 3.0 * std_nps
# threshold 초과 시: New = Threshold + (Old - Threshold) * 0.5
nps[mask] = threshold + (nps[mask] - threshold) * 0.5
```

### 6.4 Jack Penalty

동일 열 연타 시 패널티 (Code Jack은 50% 할인):

```python
# 시간 간격에 따른 Jack Score (0.2초 이하)
if diff < 0.2:
    raw_score = 25.0 * (0.2 - diff) / 0.2
    
    # Code Jack (동일 코드 연타) 감지 시 50% 할인
    if is_code_jack:
        raw_score *= 0.5
        
jack_pen[i] = max_jack_score  # 윈도우 내 최대값
```

### 6.5 Chord Strain

코드 두께 (log 스케일):

```python
for t, count in time_counts.items():
    if count > 1:
        chord_strain_val += (count - 1)
        
chord_strain[i] = np.log1p(chord_strain_val)  # log(1 + x)
```

### 6.6 Hand Strain & Alt Cost

좌우 손 밸런스 분석:

```python
# SP: 1,2,3 = 왼손, 5,6,7 = 오른손, 4 = 균형
# DP: 1-7 = 1P(왼손), 8-15 = 2P(오른손)

hand_strain[i] = max(l_actions, r_actions) / window_size
alt_cost[i] = abs(l_actions - r_actions) / window_size
```

---

## 7. 그래프 출력 (main_gui.py)

### 7.1 그래프 데이터 소스

그래프는 `calc.py`의 결과를 사용:

```python
# calc.compute_map_difficulty() 또는 new_calc 결과에서:
result = {
    'b_t': [...],    # Load (각 윈도우의 난이도 부하)
    'ema_S': [...],  # EMA_S (Burst - 순간 최대 밀도)
    'ema_L': [...],  # EMA_L (Endurance - 장기 지구력)
    ...
}
```

### 7.2 그래프 그리기

```python
# matplotlib 사용
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# Figure 생성 (DPI 100)
self.fig, self.ax = plt.subplots(figsize=(8, 4), dpi=100)
self.canvas = FigureCanvasTkAgg(self.fig, master=bottom_frame)

# 그래프 플롯
t = np.arange(len(result['b_t']))  # X축: 시간(초, 1초 윈도우)
self.ax.clear()
self.ax.plot(t, result['b_t'], label='Load (b_t)', alpha=0.5)
self.ax.plot(t, result['ema_S'], label='EMA_S (Burst)', linestyle='--')
self.ax.plot(t, result['ema_L'], label='EMA_L (Endurance)', linestyle=':')

# 꾸미기
self.ax.set_title("Difficulty Load over Time")
self.ax.set_xlabel("Time (s)")
self.ax.set_ylabel("Load")
self.ax.legend()
self.canvas.draw()
```

### 7.3 그래프 구성 요소

| 라인 | 데이터 | 스타일 | 의미 |
|------|--------|--------|------|
| Load (b_t) | `result['b_t']` | 실선, alpha=0.5 | 각 윈도우의 원시 난이도 부하 |
| EMA_S (Burst) | `result['ema_S']` | 점선 `--` | 순간 밀도 (빠른 반응) |
| EMA_L (Endurance) | `result['ema_L']` | 점선 `:` | 장기 지구력 (느린 반응) |

### 7.4 NPS Linear 모델 사용 시

NPS Linear 모델(`new_calc.py`) 사용 시에도 동일한 그래프 표시:
- `b_t` = `metrics['nps']` (Action NPS)
- `ema_S` = `metrics['nps']` (동일)
- `ema_L` = `metrics['nps']` (동일)

---

## 검증 결과

### BMS/OSU 파싱 일치 테스트 (2025-12-10)

| 파일 | BMS 노트 | OSU 노트 | NPS | 시간 차이 | NPS Std | Peak NPS | 결과 |
|------|---------|---------|-----|---------|---------|----------|------|
| CircusGalop [10K] | 12,326 | 12,326 | 51.75 | 0.0ms | 27.6422 | 176 | ✅ 완벽 일치 |

---

> **문서 관리 규칙**:
> - 이 문서의 로직 변경 시 반드시 사유 기록
> - 채널 매핑, NPS 공식, 노트 타입 정의는 **절대 기준**
> - 변경 전 `Memory for ai and Human Worker.txt`에 기록 필수
