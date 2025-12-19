# BMS Difficulty Calculator (v0.2)

10키 리듬게임 채보(BMS/Osu!mania)용 과학적 난이도 계산기

## 주요 기능

### 난이도 계산 모델
- **NPS 선형 회귀 모델** (권장): 3-feature 기반, MAE 1.12
  - Global NPS, NPS 표준편차, Chord 평균 사용
- **Legacy 모델**: NPS, LN, Jack, Roll, Alt, Hand, Chord 복합 가중치

### 파서 지원
- **BMS/BME/BML**: 7K~14K, DP, LN (LNOBJ/LNTYPE 지원)
- **Osu!mania**: 4K~18K, Hold Note 지원

### 분석 도구
- HP9 생존 분석 및 Qwilight 변환
- 디버그 모드 (노트별 메트릭 확인)
- Peak NPS (±500ms 로컬 밀도)
- 📂 **[verify/](verify/)**: 분석/검증 도구 모음 (사용 전 경로 수정 필요)

## 설치 및 사용법

1. `dist` 폴더에서 최신 릴리즈 다운로드
2. `BMSCalculator.exe` 실행
3. 파일 선택 (.bms/.bme/.osu) → Calculate

## 문서

| 문서 | 설명 |
|------|------|
| [핵심 로직 참조](docs/core_logic_reference.md) | 파서 채널 매핑, NPS 공식, 노트 타입 (절대 기준) |
| [구현 상세](docs/implementation_details.md) | 난이도 모델, HP 모델 설명 |
| [Memory](Memory%20for%20ai%20and%20Human%20Worker.txt) | 작업 히스토리 및 메모 |

## 최신 업데이트 (v0.2)

### 2025-12-08
- **NPS 선형 모델 도입**: 3-feature 모델로 MAE 1.70 → 1.12 개선
- **Peak NPS 계산 방식 변경**: 1초 윈도우 → ±500ms 로컬 밀도
- **BMS 파서 수정**: 2P 채널(27, 67) 및 풋페달(17, 57) 추가
- **핵심 로직 문서화**: `docs/core_logic_reference.md` 생성
- **디버그 모드 추가**: GUI에서 노트별 메트릭 확인 가능
- **Debug OSU 내보내기**: 메트릭을 osu 에디터에서 시각화

## 개발자 노트

```bash
# 빌드
pyinstaller BMSCalculator.spec

# 분석/검증 도구 실행 (verify 폴더 내)
cd verify
python optimize_weights.py
python optimize_bms_only.py
```

## 크레딧
Developed by Gemini & User


