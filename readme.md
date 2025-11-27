# BMS Difficulty Calculator

BMS 및 Osu!mania 파일을 위한 난이도 계산기입니다.

## 주요 기능
- **다중 포맷 지원**: `.bms`, `.bme`, `.osu` 파일 파싱.
- **상세 분석**: NPS, LN Strain, Jack, Alt Cost 등 다양한 메트릭 분석.
- **난이도 모델**: Endurance(체력)와 Burst(순간 난이도)를 고려한 독자적인 난이도 산출.
- **HP 시뮬레이션**: Osu!mania HP9 게이지 기준 생존 가능성 예측.
- **Qwilight 연동**: Qwilight 플레이 결과를 입력하여 통합 난이도 계산.

## 실행 방법
```bash
python main_gui.py
```

## 문서
상세한 구현 내용은 [docs/implementation_details.md](docs/implementation_details.md)를 참고하세요.

## 요구 사항
- Python 3.x
- numpy
- matplotlib
- tkinter (보통 Python에 내장됨)
