# 분석/검증 도구 모음

이 폴더에는 난이도 계산기의 분석 및 검증 도구들이 포함되어 있습니다.

## ⚠️ 사용 전 주의사항

**모든 스크립트는 사용 전 절대 경로를 수정해야 합니다!**

각 `.py` 파일을 열어서 파일 경로, 데이터셋 경로 등을 본인 환경에 맞게 수정하세요.

예시:
```python
# 수정 전
TARGET_DIR = "d:\\계산기\\패턴 모음"

# 수정 후 (본인 경로에 맞게)
TARGET_DIR = "C:\\Users\\YourName\\계산기\\패턴 모음"
```

---

## 📂 파일 목록

### 최적화 도구
| 파일 | 설명 |
|------|------|
| `optimize_weights.py` | 전체 가중치 최적화 |
| `optimize_bms_only.py` | BMS 전용 최적화 |
| `optimize_weights_segmented.py` | 구간별 가중치 최적화 |
| `calibrate_levels.py` | 레벨 보정 |

### 분석 도구
| 파일 | 설명 |
|------|------|
| `ablation_study.py` | Feature 제거 실험 |
| `analyze_outlier.py` | 아웃라이어 분석 |
| `analyze_residuals.py` | 잔차 분석 |
| `explore_linear_features.py` | 선형 피쳐 탐색 |

### 내보내기 도구
| 파일 | 설명 |
|------|------|
| `export_all_predicted.py` | 전체 예측 레벨 내보내기 |
| `export_predicted_levels.py` | 예측 레벨 CSV 내보내기 |

### 검증 도구
| 파일 | 설명 |
|------|------|
| `verify_calc_split.py` | 계산 분할 검증 |
| `verify_correction.py` | 보정 로직 검증 |
| `verify_dp.py` | DP(더블플레이) 검증 |
| `verify_logic.py` | 로직 검증 |
| `verify_osu.py` | Osu 파서 검증 |
| `verify_pattern_level.py` | 패턴 레벨 검증 |
| `verify_s_rank_binomial.py` | S랭크 이항분포 검증 |
| `verify_uncap.py` | Uncap 레벨 검증 |
| `reproduce_issue.py` | 이슈 재현용 |

---

## 🔧 실행 방법

```bash
# 가상환경 활성화 후
cd verify
python <스크립트명>.py
```
