"""
NPS 테스트 파일 분석 스크립트
문제분석용 폴더의 .osu 및 .bms 파일들의 NPS, 총 노트수, 곡 길이를 분석합니다.
"""
import os
from bms_parser import BMSParser
from osu_parser import OsuParser

def analyze_file(filepath):
    """파일을 파싱하고 기본 정보를 추출합니다."""
    ext = os.path.splitext(filepath)[1].lower()
    
    try:
        if ext == '.bms':
            parser = BMSParser(filepath)
            notes = parser.parse()
            
            # 총 노트수
            total_notes = len(notes)
            
            # 곡 길이 계산 (첫 노트부터 마지막 노트까지)
            if notes:
                first_time = notes[0]['time']
                last_time = notes[-1]['time']
                song_length = last_time - first_time
                if song_length < 1.0:
                    song_length = 1.0
            else:
                song_length = 0
                
        elif ext == '.osu':
            parser = OsuParser(filepath)
            notes = parser.parse()
            
            # 총 노트수
            total_notes = len(notes)
            
            # 곡 길이 (parser.duration 이미 계산됨)
            song_length = parser.duration
            
        else:
            return None
        
        # NPS 계산
        nps = total_notes / song_length if song_length > 0 else 0
        
        return {
            'filename': os.path.basename(filepath),
            'total_notes': total_notes,
            'song_length': song_length,
            'nps': nps,
            'format': ext[1:].upper()
        }
    except Exception as e:
        print(f"오류 발생 [{os.path.basename(filepath)}]: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def main():
    folder_path = r'd:\계산기\문제분석용'
    
    # 파일 목록
    files = [
        'Collection - Piano Beatmap Set (CircusGalop) [10K HELL CIRCUS].bms',
        'Collection - Piano Beatmap Set (CircusGalop) [10K HELL CIRCUS].osu',
        'debug.bms'
    ]
    
    print("=" * 80)
    print("NPS 테스트 파일 분석 결과")
    print("=" * 80)
    print()
    
    results = []
    for filename in files:
        filepath = os.path.join(folder_path, filename)
        if os.path.exists(filepath):
            result = analyze_file(filepath)
            if result:
                results.append(result)
    
    # 결과 출력
    for result in results:
        print(f"파일명: {result['filename']}")
        print(f"  형식: {result['format']}")
        print(f"  총 노트수: {result['total_notes']:,}개")
        print(f"  곡 길이: {result['song_length']:.2f}초 ({result['song_length']/60:.2f}분)")
        print(f"  NPS: {result['nps']:.2f}")
        print()
    
    print("=" * 80)
    
    # BMS와 OSU 비교 (동일한 곡인 경우)
    bms_results = [r for r in results if r['format'] == 'BMS']
    osu_results = [r for r in results if r['format'] == 'OSU']
    
    if bms_results and osu_results:
        print("\n[BMS vs OSU 비교 분석]")
        print("=" * 80)
        
        # CircusGalop 파일 비교
        circus_bms = [r for r in bms_results if 'CircusGalop' in r['filename']]
        circus_osu = [r for r in osu_results if 'CircusGalop' in r['filename']]
        
        if circus_bms and circus_osu:
            bms = circus_bms[0]
            osu = circus_osu[0]
            
            print(f"\n곡명: CircusGalop [10K HELL CIRCUS]")
            print(f"  BMS 총 노트수: {bms['total_notes']:,}개")
            print(f"  OSU 총 노트수: {osu['total_notes']:,}개")
            print(f"  노트수 차이: {abs(bms['total_notes'] - osu['total_notes']):,}개")
            print()
            print(f"  BMS 곡 길이: {bms['song_length']:.2f}초")
            print(f"  OSU 곡 길이: {osu['song_length']:.2f}초")
            print(f"  곡 길이 차이: {abs(bms['song_length'] - osu['song_length']):.2f}초")
            print()
            print(f"  BMS NPS: {bms['nps']:.2f}")
            print(f"  OSU NPS: {osu['nps']:.2f}")
            print(f"  NPS 차이: {abs(bms['nps'] - osu['nps']):.2f}")
            print(f"  NPS 비율: {(osu['nps'] / bms['nps'] * 100):.2f}% (OSU/BMS)")
        
        print("=" * 80)

if __name__ == '__main__':
    main()
