"""
기상청 날씨 API 통합 모듈
Korea Meteorological Administration Weather API Integration

주의: 단기예보와 중기예보는 서로 다른 API입니다!
1. 단기예보 API (VilageFcstInfoService_2.0)
2. 중기예보 API (MidFcstInfoService)
"""

import requests
from datetime import datetime, timedelta
from functools import lru_cache
import os

# 지역 코드 설정 import
from weather_config import (
    SHORT_TERM_API_KEY,
    MID_TERM_API_KEY,
    MID_FORECAST_REGIONS,
    MID_LAND_REGIONS,
    MID_TEMP_REGIONS,
    SHORT_FORECAST_COORDS,
    DEFAULT_REGION,
    DEFAULT_MID_FORECAST,
    DEFAULT_MID_LAND,
    DEFAULT_MID_TEMP,
    DEFAULT_SHORT_COORDS
)

# API 키 (환경변수 우선, 없으면 config 파일 사용)
SHORT_API_KEY = "334bf3bdbd19cdcdb0d4363e2bd1030eb40c1f148e798d9493e0a10c27e8b286"
MID_API_KEY = "334bf3bdbd19cdcdb0d4363e2bd1030eb40c1f148e798d9493e0a10c27e8b286"

# 기본 URL
SHORT_TERM_BASE_URL = "http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0"
MID_TERM_BASE_URL = "http://apis.data.go.kr/1360000/MidFcstInfoService"

# API 엔드포인트
ENDPOINTS = {
    # 단기예보 API 엔드포인트
    "short_forecast": f"{SHORT_TERM_BASE_URL}/getVilageFcst",
    "ultra_short_now": f"{SHORT_TERM_BASE_URL}/getUltraSrtNcst",
    "ultra_short_fcst": f"{SHORT_TERM_BASE_URL}/getUltraSrtFcst",
    
    # 중기예보 API 엔드포인트
    "mid_forecast": f"{MID_TERM_BASE_URL}/getMidFcst",
    "mid_land": f"{MID_TERM_BASE_URL}/getMidLandFcst",
    "mid_temp": f"{MID_TERM_BASE_URL}/getMidTa",
}


# ============================================
# 1. 초단기 실황 (현재 날씨) - 단기예보 API
# ============================================

@lru_cache(maxsize=10)
def get_current_weather(cache_key, region=DEFAULT_REGION):
    """
    현재 날씨 실황 조회
    매시간 정시에 생성, 10분마다 업데이트
    API: 단기예보 API (VilageFcstInfoService)
    """
    try:
        coords = SHORT_FORECAST_COORDS.get(region, DEFAULT_SHORT_COORDS)
        now = datetime.now()
        
        # 발표시각: 매 정시 (00:00, 01:00, ...)
        base_time = now.strftime("%H00")
        base_date = now.strftime("%Y%m%d")
        
        params = {
            "serviceKey": SHORT_API_KEY,  # 단기예보 API 키 사용
            "numOfRows": 10,
            "pageNo": 1,
            "dataType": "JSON",
            "base_date": base_date,
            "base_time": base_time,
            "nx": coords["nx"],
            "ny": coords["ny"]
        }
        
        response = requests.get(ENDPOINTS["ultra_short_now"], params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        # 응답 파싱
        if data.get("response", {}).get("header", {}).get("resultCode") == "00":
            items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
            
            weather_data = {}
            for item in items:
                category = item.get("category")
                value = item.get("obsrValue")
                
                if category == "T1H":  # 기온
                    weather_data["temperature"] = f"{value}°C"
                elif category == "RN1":  # 1시간 강수량
                    weather_data["rainfall"] = f"{value}mm"
                elif category == "REH":  # 습도
                    weather_data["humidity"] = f"{value}%"
                elif category == "WSD":  # 풍속
                    weather_data["wind_speed"] = f"{value}m/s"
                elif category == "PTY":  # 강수형태
                    pty_map = {
                        "0": "없음",
                        "1": "비",
                        "2": "비/눈",
                        "3": "눈",
                        "5": "빗방울",
                        "6": "빗방울눈날림",
                        "7": "눈날림"
                    }
                    weather_data["precipitation_type"] = pty_map.get(value, "없음")
            
            weather_data["region"] = region
            weather_data["update_time"] = f"{base_date} {base_time}"
            return weather_data
        else:
            return {"error": "데이터를 가져올 수 없습니다"}
            
    except Exception as e:
        print(f"Current Weather API Error: {e}")
        return {
            "temperature": "데이터 없음",
            "humidity": "데이터 없음",
            "note": "현재 날씨 정보를 불러올 수 없습니다."
        }


# ============================================
# 2. 초단기 예보 (6시간 예보) - 단기예보 API
# ============================================

@lru_cache(maxsize=10)
def get_ultra_short_forecast(cache_key, region=DEFAULT_REGION):
    """
    초단기 예보 (향후 6시간)
    매시간 30분에 생성, 45분 이후 호출
    API: 단기예보 API (VilageFcstInfoService)
    """
    try:
        coords = SHORT_FORECAST_COORDS.get(region, DEFAULT_SHORT_COORDS)
        now = datetime.now()
        
        # 발표시각: 매 30분 (00:30, 01:30, ...)
        base_time = now.strftime("%H30")
        base_date = now.strftime("%Y%m%d")
        
        params = {
            "serviceKey": SHORT_API_KEY,  # 단기예보 API 키 사용
            "numOfRows": 60,
            "pageNo": 1,
            "dataType": "JSON",
            "base_date": base_date,
            "base_time": base_time,
            "nx": coords["nx"],
            "ny": coords["ny"]
        }
        
        response = requests.get(ENDPOINTS["ultra_short_fcst"], params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        if data.get("response", {}).get("header", {}).get("resultCode") == "00":
            items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
            
            # 시간대별로 정리
            forecast_by_time = {}
            for item in items:
                fcst_time = item.get("fcstTime")
                category = item.get("category")
                value = item.get("fcstValue")
                
                if fcst_time not in forecast_by_time:
                    forecast_by_time[fcst_time] = {}
                
                if category == "T1H":
                    forecast_by_time[fcst_time]["temp"] = f"{value}°C"
                elif category == "SKY":
                    sky_map = {"1": "맑음", "3": "구름많음", "4": "흐림"}
                    forecast_by_time[fcst_time]["sky"] = sky_map.get(value, "알 수 없음")
                elif category == "PTY":
                    pty_map = {"0": "없음", "1": "비", "2": "비/눈", "3": "눈", "5": "빗방울", "6": "빗방울눈날림", "7": "눈날림"}
                    forecast_by_time[fcst_time]["pty"] = pty_map.get(value, "없음")
            
            return {
                "region": region,
                "forecast": forecast_by_time
            }
        else:
            return {"error": "데이터를 가져올 수 없습니다"}
            
    except Exception as e:
        print(f"Ultra Short Forecast API Error: {e}")
        return {"error": "초단기 예보를 불러올 수 없습니다."}


# ============================================
# 3. 단기예보 (3일 예보) - 단기예보 API
# ============================================

@lru_cache(maxsize=10)
def get_short_forecast(cache_key, region=DEFAULT_REGION):
    """
    단기예보 (3일)
    하루 8회 발표: 02, 05, 08, 11, 14, 17, 20, 23시
    API: 단기예보 API (VilageFcstInfoService)
    """
    try:
        coords = SHORT_FORECAST_COORDS.get(region, DEFAULT_SHORT_COORDS)
        now = datetime.now()
        
        # 가장 최근 발표 시각 계산
        base_times = ["0200", "0500", "0800", "1100", "1400", "1700", "2000", "2300"]
        current_hour = now.hour
        
        # 적절한 base_time 찾기
        if current_hour < 2:
            base_time = "2300"
            base_date = (now - timedelta(days=1)).strftime("%Y%m%d")
        else:
            for i, bt in enumerate(["02", "05", "08", "11", "14", "17", "20", "23"]):
                if current_hour >= int(bt):
                    base_time = bt + "00"
                    base_date = now.strftime("%Y%m%d")
        
        params = {
            "serviceKey": SHORT_API_KEY,  # 단기예보 API 키 사용
            "numOfRows": 100,
            "pageNo": 1,
            "dataType": "JSON",
            "base_date": base_date,
            "base_time": base_time,
            "nx": coords["nx"],
            "ny": coords["ny"]
        }
        
        response = requests.get(ENDPOINTS["short_forecast"], params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        if data.get("response", {}).get("header", {}).get("resultCode") == "00":
            items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
            
            # 날짜별로 정리
            daily_forecast = {}
            for item in items:
                fcst_date = item.get("fcstDate")
                fcst_time = item.get("fcstTime")
                category = item.get("category")
                value = item.get("fcstValue")
                
                if fcst_date not in daily_forecast:
                    daily_forecast[fcst_date] = {}
                
                if category == "TMN":  # 최저기온
                    daily_forecast[fcst_date]["min_temp"] = f"{value}°C"
                elif category == "TMX":  # 최고기온
                    daily_forecast[fcst_date]["max_temp"] = f"{value}°C"
                elif category == "POP" and "rain_prob" not in daily_forecast[fcst_date]:  # 강수확률
                    daily_forecast[fcst_date]["rain_prob"] = f"{value}%"
                elif category == "SKY" and "sky" not in daily_forecast[fcst_date]:
                    sky_map = {"1": "맑음", "3": "구름많음", "4": "흐림"}
                    daily_forecast[fcst_date]["sky"] = sky_map.get(value, "알 수 없음")
            
            return {
                "region": region,
                "daily": daily_forecast
            }
        else:
            return {"error": "데이터를 가져올 수 없습니다"}
            
    except Exception as e:
        print(f"Short Forecast API Error: {e}")
        return {"error": "단기예보를 불러올 수 없습니다."}


# ============================================
# 4. 중기예보 (4-10일 예보) - 중기예보 API
# ============================================

@lru_cache(maxsize=10)
def get_mid_forecast(cache_key, region=DEFAULT_REGION):
    """
    중기 기온 예보
    하루 2회 발표: 06시, 18시
    API: 중기예보 API (MidFcstInfoService)
    """
    try:
        region_code = MID_TEMP_REGIONS.get(region, DEFAULT_MID_TEMP)
        now = datetime.now()
        
        # 발표시각 계산
        if now.hour >= 18:
            base_time = "1800"
            base_date = now.strftime("%Y%m%d")
        elif now.hour >= 6:
            base_time = "0600"
            base_date = now.strftime("%Y%m%d")
        else:
            base_time = "1800"
            base_date = (now - timedelta(days=1)).strftime("%Y%m%d")
        
        tm_fc = f"{base_date}{base_time}"
        
        params = {
            "serviceKey": MID_API_KEY,  # 중기예보 API 키 사용
            "numOfRows": 10,
            "pageNo": 1,
            "dataType": "JSON",
            "regId": region_code,
            "tmFc": tm_fc
        }
        
        response = requests.get(ENDPOINTS["mid_temp"], params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        if data.get("response", {}).get("header", {}).get("resultCode") == "00":
            items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
            
            if items:
                item = items[0]
                forecast = {}
                
                for day in range(4, 11):  # 4일~10일
                    forecast[f"day_{day}"] = {
                        "min_temp": item.get(f"taMin{day}", "N/A"),
                        "max_temp": item.get(f"taMax{day}", "N/A")
                    }
                
                return {
                    "region": region,
                    "forecast": forecast
                }
        
        return {"error": "중기예보 데이터를 가져올 수 없습니다"}
            
    except Exception as e:
        print(f"Mid Forecast API Error: {e}")
        return {"error": "중기예보를 불러올 수 없습니다."}


# ============================================
# 5. 중기 육상예보 (날씨 예보) - 중기예보 API
# ============================================

@lru_cache(maxsize=10)
def get_mid_land_forecast(cache_key, region=DEFAULT_REGION):
    """
    중기 육상 예보 (날씨, 강수확률)
    하루 2회 발표: 06시, 18시
    API: 중기예보 API (MidFcstInfoService)
    """
    try:
        # 지역에 맞는 육상예보 코드 매핑
        region_mapping = {
            "제주": "제주",
            "서귀포": "제주",
            "제주시": "제주",
            "서울": "서울_인천_경기",
            "인천": "서울_인천_경기",
            "경기": "서울_인천_경기",
        }
        
        mapped_region = region_mapping.get(region, "제주")
        region_code = MID_LAND_REGIONS.get(mapped_region, DEFAULT_MID_LAND)
        
        now = datetime.now()
        
        # 발표시각 계산
        if now.hour >= 18:
            base_time = "1800"
            base_date = now.strftime("%Y%m%d")
        elif now.hour >= 6:
            base_time = "0600"
            base_date = now.strftime("%Y%m%d")
        else:
            base_time = "1800"
            base_date = (now - timedelta(days=1)).strftime("%Y%m%d")
        
        tm_fc = f"{base_date}{base_time}"
        
        params = {
            "serviceKey": MID_API_KEY,  # 중기예보 API 키 사용
            "numOfRows": 10,
            "pageNo": 1,
            "dataType": "JSON",
            "regId": region_code,
            "tmFc": tm_fc
        }
        
        response = requests.get(ENDPOINTS["mid_land"], params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        if data.get("response", {}).get("header", {}).get("resultCode") == "00":
            items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
            
            if items:
                item = items[0]
                forecast = {}
                
                # 4일~10일 예보
                for day in range(4, 11):
                    if day <= 7:
                        forecast[f"day_{day}"] = {
                            "am_weather": item.get(f"wf{day}Am", "N/A"),
                            "pm_weather": item.get(f"wf{day}Pm", "N/A"),
                            "am_rain_prob": item.get(f"rnSt{day}Am", "N/A"),
                            "pm_rain_prob": item.get(f"rnSt{day}Pm", "N/A")
                        }
                    else:
                        forecast[f"day_{day}"] = {
                            "weather": item.get(f"wf{day}", "N/A"),
                            "rain_prob": item.get(f"rnSt{day}", "N/A")
                        }
                
                return {
                    "region": mapped_region,
                    "forecast": forecast
                }
        
        return {"error": "중기 육상예보 데이터를 가져올 수 없습니다"}
            
    except Exception as e:
        print(f"Mid Land Forecast API Error: {e}")
        return {"error": "중기 육상예보를 불러올 수 없습니다."}


# ============================================
# 통합 함수
# ============================================

def get_weather_for_context(region=DEFAULT_REGION):
    """
    농민 챗봇용 날씨 정보 통합
    단기예보 API와 중기예보 API 모두 사용
    """
    cache_key = datetime.now().strftime("%Y%m%d%H")
    
    try:
        # 단기예보 API로 현재 날씨와 3일 예보
        current = get_current_weather(cache_key, region)
        short = get_short_forecast(cache_key, region)
        
        context = f"""
현재 {region} 날씨:
- 기온: {current.get('temperature', 'N/A')}
- 습도: {current.get('humidity', 'N/A')}
- 강수: {current.get('rainfall', 'N/A')}
- 하늘상태: {current.get('precipitation_type', 'N/A')}

"""
        
        if short.get("daily"):
            context += "3일 예보:\n"
            for date, info in list(short["daily"].items())[:3]:
                context += f"  {date}: 최저 {info.get('min_temp', 'N/A')}, 최고 {info.get('max_temp', 'N/A')}, "
                context += f"강수확률 {info.get('rain_prob', 'N/A')}, {info.get('sky', 'N/A')}\n"
        
        return context.strip()
    
    except Exception as e:
        print(f"Weather Context Error: {e}")
        return f"{region} 날씨 정보를 가져올 수 없습니다."


# ============================================
# 테스트 함수
# ============================================

if __name__ == "__main__":
    print("=== 기상청 API 테스트 ===\n")
    print(f"단기예보 API 키: {SHORT_API_KEY[:20]}...")
    print(f"중기예보 API 키: {MID_API_KEY[:20]}...\n")
    
    test_region = "제주"
    
    print("1. 현재 날씨 (단기예보 API):")
    current = get_current_weather(datetime.now().strftime("%Y%m%d%H"), test_region)
    print(current)
    print()
    
    print("2. 단기예보 (단기예보 API):")
    short = get_short_forecast(datetime.now().strftime("%Y%m%d%H"), test_region)
    print(short)
    print()
    
    print("3. 중기기온 (중기예보 API):")
    mid = get_mid_forecast(datetime.now().strftime("%Y%m%d%H"), test_region)
    print(mid)
    print()
    
    print("4. 통합 컨텍스트:")
    context = get_weather_for_context(test_region)
    print(context)



# ============================================
# 2. 초단기 예보 (6시간 예보)
# ============================================

@lru_cache(maxsize=10)
def get_ultra_short_forecast(cache_key, region=DEFAULT_REGION):
    """
    초단기 예보 (향후 6시간)
    매시간 30분에 생성, 45분 이후 호출
    """
    try:
        coords = SHORT_FORECAST_COORDS.get(region, DEFAULT_SHORT_COORDS)
        now = datetime.now()
        
        # 발표시각: 매 30분 (00:30, 01:30, ...)
        base_time = now.strftime("%H30")
        base_date = now.strftime("%Y%m%d")
        
        params = {
            "serviceKey": SHORT_API_KEY,
            "numOfRows": 60,
            "pageNo": 1,
            "dataType": "JSON",
            "base_date": base_date,
            "base_time": base_time,
            "nx": coords["nx"],
            "ny": coords["ny"]
        }
        
        response = requests.get(ENDPOINTS["ultra_short_fcst"], params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        if data.get("response", {}).get("header", {}).get("resultCode") == "00":
            items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
            
            # 시간대별로 정리
            forecast_by_time = {}
            for item in items:
                fcst_time = item.get("fcstTime")
                category = item.get("category")
                value = item.get("fcstValue")
                
                if fcst_time not in forecast_by_time:
                    forecast_by_time[fcst_time] = {}
                
                if category == "T1H":
                    forecast_by_time[fcst_time]["temp"] = f"{value}°C"
                elif category == "SKY":
                    sky_map = {"1": "맑음", "3": "구름많음", "4": "흐림"}
                    forecast_by_time[fcst_time]["sky"] = sky_map.get(value, "알 수 없음")
                elif category == "PTY":
                    pty_map = {"0": "없음", "1": "비", "2": "비/눈", "3": "눈", "5": "빗방울", "6": "빗방울눈날림", "7": "눈날림"}
                    forecast_by_time[fcst_time]["pty"] = pty_map.get(value, "없음")
            
            return {
                "region": region,
                "forecast": forecast_by_time
            }
        else:
            return {"error": "데이터를 가져올 수 없습니다"}
            
    except Exception as e:
        print(f"Ultra Short Forecast API Error: {e}")
        return {"error": "초단기 예보를 불러올 수 없습니다."}


# ============================================
# 3. 단기예보 (3일 예보)
# ============================================

@lru_cache(maxsize=10)
def get_short_forecast(cache_key, region=DEFAULT_REGION):
    """
    단기예보 (3일)
    하루 8회 발표: 02, 05, 08, 11, 14, 17, 20, 23시
    """
    try:
        coords = SHORT_FORECAST_COORDS.get(region, DEFAULT_SHORT_COORDS)
        now = datetime.now()
        
        # 가장 최근 발표 시각 계산
        base_times = ["0200", "0500", "0800", "1100", "1400", "1700", "2000", "2300"]
        current_hour = now.hour
        
        # 적절한 base_time 찾기
        if current_hour < 2:
            base_time = "2300"
            base_date = (now - timedelta(days=1)).strftime("%Y%m%d")
        else:
            for i, bt in enumerate(["02", "05", "08", "11", "14", "17", "20", "23"]):
                if current_hour >= int(bt):
                    base_time = bt + "00"
                    base_date = now.strftime("%Y%m%d")
        
        params = {
            "serviceKey": SHORT_API_KEY,
            "numOfRows": 100,
            "pageNo": 1,
            "dataType": "JSON",
            "base_date": base_date,
            "base_time": base_time,
            "nx": coords["nx"],
            "ny": coords["ny"]
        }
        
        response = requests.get(ENDPOINTS["short_forecast"], params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        if data.get("response", {}).get("header", {}).get("resultCode") == "00":
            items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
            
            # 날짜별로 정리
            daily_forecast = {}
            for item in items:
                fcst_date = item.get("fcstDate")
                fcst_time = item.get("fcstTime")
                category = item.get("category")
                value = item.get("fcstValue")
                
                if fcst_date not in daily_forecast:
                    daily_forecast[fcst_date] = {}
                
                if category == "TMN":  # 최저기온
                    daily_forecast[fcst_date]["min_temp"] = f"{value}°C"
                elif category == "TMX":  # 최고기온
                    daily_forecast[fcst_date]["max_temp"] = f"{value}°C"
                elif category == "POP" and "rain_prob" not in daily_forecast[fcst_date]:  # 강수확률
                    daily_forecast[fcst_date]["rain_prob"] = f"{value}%"
                elif category == "SKY" and "sky" not in daily_forecast[fcst_date]:
                    sky_map = {"1": "맑음", "3": "구름많음", "4": "흐림"}
                    daily_forecast[fcst_date]["sky"] = sky_map.get(value, "알 수 없음")
            
            return {
                "region": region,
                "daily": daily_forecast
            }
        else:
            return {"error": "데이터를 가져올 수 없습니다"}
            
    except Exception as e:
        print(f"Short Forecast API Error: {e}")
        return {"error": "단기예보를 불러올 수 없습니다."}


# ============================================
# 4. 중기예보 (4-10일 예보)
# ============================================

@lru_cache(maxsize=10)
def get_mid_forecast(cache_key, region=DEFAULT_REGION):
    """
    중기 기온 예보
    하루 2회 발표: 06시, 18시
    """
    try:
        region_code = MID_TEMP_REGIONS.get(region, DEFAULT_MID_TEMP)
        now = datetime.now()
        
        # 발표시각 계산
        if now.hour >= 18:
            base_time = "1800"
            base_date = now.strftime("%Y%m%d")
        elif now.hour >= 6:
            base_time = "0600"
            base_date = now.strftime("%Y%m%d")
        else:
            base_time = "1800"
            base_date = (now - timedelta(days=1)).strftime("%Y%m%d")
        
        tm_fc = f"{base_date}{base_time}"
        
        params = {
            "serviceKey": MID_API_KEY,
            "numOfRows": 10,
            "pageNo": 1,
            "dataType": "JSON",
            "regId": region_code,
            "tmFc": tm_fc
        }
        
        response = requests.get(ENDPOINTS["mid_temp"], params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        if data.get("response", {}).get("header", {}).get("resultCode") == "00":
            items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
            
            if items:
                item = items[0]
                forecast = {}
                
                for day in range(4, 11):  # 4일~10일
                    forecast[f"day_{day}"] = {
                        "min_temp": item.get(f"taMin{day}", "N/A"),
                        "max_temp": item.get(f"taMax{day}", "N/A")
                    }
                
                return {
                    "region": region,
                    "forecast": forecast
                }
        
        return {"error": "중기예보 데이터를 가져올 수 없습니다"}
            
    except Exception as e:
        print(f"Mid Forecast API Error: {e}")
        return {"error": "중기예보를 불러올 수 없습니다."}


# ============================================
# 5. 중기 육상예보 (날씨 예보)
# ============================================

@lru_cache(maxsize=10)
def get_mid_land_forecast(cache_key, region=DEFAULT_REGION):
    """
    중기 육상 예보 (날씨, 강수확률)
    하루 2회 발표: 06시, 18시
    """
    try:
        # 지역에 맞는 육상예보 코드 매핑
        region_mapping = {
            "제주": "제주",
            "서귀포": "제주",
            "제주시": "제주",
            "서울": "서울_인천_경기",
            "인천": "서울_인천_경기",
            "경기": "서울_인천_경기",
        }
        
        mapped_region = region_mapping.get(region, "제주")
        region_code = MID_LAND_REGIONS.get(mapped_region, DEFAULT_MID_LAND)
        
        now = datetime.now()
        
        # 발표시각 계산
        if now.hour >= 18:
            base_time = "1800"
            base_date = now.strftime("%Y%m%d")
        elif now.hour >= 6:
            base_time = "0600"
            base_date = now.strftime("%Y%m%d")
        else:
            base_time = "1800"
            base_date = (now - timedelta(days=1)).strftime("%Y%m%d")
        
        tm_fc = f"{base_date}{base_time}"
        
        params = {
            "serviceKey": MID_API_KEY,
            "numOfRows": 10,
            "pageNo": 1,
            "dataType": "JSON",
            "regId": region_code,
            "tmFc": tm_fc
        }
        
        response = requests.get(ENDPOINTS["mid_land"], params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        if data.get("response", {}).get("header", {}).get("resultCode") == "00":
            items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
            
            if items:
                item = items[0]
                forecast = {}
                
                # 4일~10일 예보
                for day in range(4, 11):
                    if day <= 7:
                        forecast[f"day_{day}"] = {
                            "am_weather": item.get(f"wf{day}Am", "N/A"),
                            "pm_weather": item.get(f"wf{day}Pm", "N/A"),
                            "am_rain_prob": item.get(f"rnSt{day}Am", "N/A"),
                            "pm_rain_prob": item.get(f"rnSt{day}Pm", "N/A")
                        }
                    else:
                        forecast[f"day_{day}"] = {
                            "weather": item.get(f"wf{day}", "N/A"),
                            "rain_prob": item.get(f"rnSt{day}", "N/A")
                        }
                
                return {
                    "region": mapped_region,
                    "forecast": forecast
                }
        
        return {"error": "중기 육상예보 데이터를 가져올 수 없습니다"}
            
    except Exception as e:
        print(f"Mid Land Forecast API Error: {e}")
        return {"error": "중기 육상예보를 불러올 수 없습니다."}


# ============================================
# 통합 함수
# ============================================

def get_weather_for_context(region=DEFAULT_REGION):
    """
    농민 챗봇용 날씨 정보 통합
    """
    cache_key = datetime.now().strftime("%Y%m%d%H")
    
    try:
        current = get_current_weather(cache_key, region)
        short = get_short_forecast(cache_key, region)
        
        context = f"""
현재 {region} 날씨:
- 기온: {current.get('temperature', 'N/A')}
- 습도: {current.get('humidity', 'N/A')}
- 강수: {current.get('rainfall', 'N/A')}
- 하늘상태: {current.get('precipitation_type', 'N/A')}

"""
        
        if short.get("daily"):
            context += "3일 예보:\n"
            for date, info in list(short["daily"].items())[:3]:
                context += f"  {date}: 최저 {info.get('min_temp', 'N/A')}, 최고 {info.get('max_temp', 'N/A')}, "
                context += f"강수확률 {info.get('rain_prob', 'N/A')}, {info.get('sky', 'N/A')}\n"
        
        return context.strip()
    
    except Exception as e:
        print(f"Weather Context Error: {e}")
        return f"{region} 날씨 정보를 가져올 수 없습니다."


# ============================================
# 테스트 함수
# ============================================

if __name__ == "__main__":
    print("=== 기상청 API 테스트 ===\n")
    
    test_region = "제주"
    
    print("1. 현재 날씨:")
    current = get_current_weather(datetime.now().strftime("%Y%m%d%H"), test_region)
    print(current)
    print()
    
    print("2. 단기예보:")
    short = get_short_forecast(datetime.now().strftime("%Y%m%d%H"), test_region)
    print(short)
    print()
    
    print("3. 통합 컨텍스트:")
    context = get_weather_for_context(test_region)
    print(context)