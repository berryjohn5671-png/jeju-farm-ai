from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import requests
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()
import os

# 기상청 API import
from weather_api import (
    get_weather_for_context, 
    get_mid_forecast,
    get_mid_land_forecast,
    SHORT_FORECAST_COORDS
)

app = Flask(__name__)
CORS(app)

MODEL_NAME = "google/gemma-3-27b-it:free"
LINK = "https://openrouter.ai/api/v1/chat/completions"
API_KEY = os.getenv("OPENROUTER_API_KEY")

print(API_KEY)

# 기상청 API 키 설정
# 두 개의 다른 API이므로 각각 발급받아야 합니다!

# 방법 1: 환경변수로 설정 (권장)
# export KMA_SHORT_API_KEY="여기에_단기예보_API_키"
# export KMA_MID_API_KEY="여기에_중기예보_API_키"

# 방법 2: weather_config.py 파일에 직접 입력
# weather_config.py 파일을 열어서 API 키 입력



# 환경변수 우선, 없으면 config 파일 사용


# ============================================
# FARMING KNOWLEDGE BASE
# ============================================

def get_farming_calendar():
    """현재 월 기준 농사 정보"""
    month = datetime.now().month
    
    calendar_data = {
        1: {
            "tasks": ["수확 마무리", "전정 준비", "동해 방지"],
            "tips": "동해 방지를 위해 수분 관리가 중요합니다"
        },
        2: {
            "tasks": ["전정 작업", "토양 개량", "유기질 비료 투입"],
            "tips": "2월 중순까지 전정 완료가 필요합니다"
        },
        3: {
            "tasks": ["봄 거름 주기", "병해충 예방 약제 살포"],
            "tips": "새순이 나오기 전 방제를 완료하세요"
        },
        4: {
            "tasks": ["개화 관리", "수분 관리", "적화"],
            "tips": "꽃이 지면서 착과가 시작됩니다"
        },
        5: {
            "tasks": ["적과 1차", "관수 시작", "웃거름"],
            "tips": "과다 착과 시 적과가 필수입니다"
        },
        6: {
            "tasks": ["적과 2차", "여름 거름", "초생재배 관리"],
            "tips": "고온기 물 관리가 중요합니다"
        },
        7: {
            "tasks": ["태풍 대비", "병해충 집중 방제", "배수로 점검"],
            "tips": "태풍 시기, 지주를 점검하세요"
        },
        8: {
            "tasks": ["가뭄 대비 관수", "여름 순 제거"],
            "tips": "고온 스트레스에 주의하세요"
        },
        9: {
            "tasks": ["가을 거름", "착색 관리 시작", "과실 비대"],
            "tips": "착색기 질소 과다를 주의하세요"
        },
        10: {
            "tasks": ["수확 준비", "당도 체크", "착색 촉진"],
            "tips": "극조생종 수확이 시작됩니다"
        },
        11: {
            "tasks": ["본격 수확", "저장고 관리", "선별 작업"],
            "tips": "조생종 수확 적기입니다"
        },
        12: {
            "tasks": ["수확 지속", "저장 관리", "월동 준비"],
            "tips": "보통종 수확이 시작됩니다"
        }
    }
    
    return calendar_data.get(month, {})


def get_pest_alerts():
    """계절별 병해충 정보"""
    month = datetime.now().month
    
    if month in [5, 6, 7, 8]:
        return {
            "high_risk": ["응애", "깍지벌레", "귤녹응애"],
            "prevention": "고온다습한 여름철, 병해충 발생이 많습니다. 주 1회 과수원 점검과 예방 방제를 권장합니다."
        }
    else:
        return {
            "high_risk": ["궤양병"],
            "prevention": "비교적 병해충 발생이 적은 시기입니다. 정기 점검을 유지하세요."
        }


def get_soil_recommendations():
    """계절별 토양 관리"""
    month = datetime.now().month
    
    if month in [3, 4, 5]:
        return "봄철에는 석회 비료로 토양 pH를 5.5-6.5로 조정하고, 유기질 비료를 충분히 투입하세요."
    elif month in [6, 7, 8]:
        return "여름철에는 멀칭으로 토양 수분을 유지하고, 배수가 잘 되도록 관리하세요."
    elif month in [9, 10, 11]:
        return "가을철에는 수확 전 칼륨 비료를 추가하여 당도를 높이고, 착색을 개선하세요."
    else:
        return "겨울철에는 동해 방지를 위해 토양 피복과 수분 관리에 신경 쓰세요."


# ============================================
# CONTEXT BUILDER
# ============================================

def build_context_for_llm(user_question, region="제주"):
    """사용자 질문에 맞는 컨텍스트 구성"""
    context_parts = []
    question_lower = user_question.lower()
    
    # 날씨 관련 키워드 확인
    weather_keywords = ["날씨", "기온", "비", "온도", "습도", "바람", "강수", "예보", "주간", "이번주", "다음주"]
    is_weather_question = any(word in question_lower for word in weather_keywords)
    
    # 1. 날씨 정보 (날씨 관련 질문이면 포함)
    if is_weather_question:
        try:
            # 현재 날씨 + 단기예보 (3일)
            weather_context = get_weather_for_context(region)
            context_parts.append(f"=== 현재 날씨 및 3일 예보 ===\n{weather_context}\n")
            
            # 중기예보 추가 (4-10일)
            cache_key = datetime.now().strftime("%Y%m%d%H")
            mid_temp = get_mid_forecast(cache_key, region)
            mid_land = get_mid_land_forecast(cache_key, region)
            
            if mid_temp and not mid_temp.get("error"):
                mid_context = "\n=== 중기예보 (4-10일 후) ===\n"
                forecast_data = mid_temp.get("forecast", {})
                
                for day_key in sorted(forecast_data.keys()):
                    day_num = day_key.replace("day_", "")
                    day_info = forecast_data[day_key]
                    min_temp = day_info.get("min_temp", "N/A")
                    max_temp = day_info.get("max_temp", "N/A")
                    mid_context += f"{day_num}일 후: 최저 {min_temp}°C, 최고 {max_temp}°C\n"
                
                # 중기 육상예보 추가
                if mid_land and not mid_land.get("error"):
                    land_data = mid_land.get("forecast", {})
                    for day_key in sorted(land_data.keys()):
                        day_num = day_key.replace("day_", "")
                        day_info = land_data[day_key]
                        
                        if "am_weather" in day_info:
                            mid_context += f"  - 오전: {day_info.get('am_weather', 'N/A')} (강수확률 {day_info.get('am_rain_prob', 'N/A')}%)\n"
                            mid_context += f"  - 오후: {day_info.get('pm_weather', 'N/A')} (강수확률 {day_info.get('pm_rain_prob', 'N/A')}%)\n"
                        elif "weather" in day_info:
                            mid_context += f"  - 날씨: {day_info.get('weather', 'N/A')} (강수확률 {day_info.get('rain_prob', 'N/A')}%)\n"
                
                context_parts.append(mid_context)
        
        except Exception as e:
            print(f"Weather API Error: {e}")
    
    # 2. 농사 달력 (항상 포함)
    calendar = get_farming_calendar()
    if calendar:
        context_parts.append(f"""
=== 이달의 농사 정보 ===
주요 작업: {', '.join(calendar['tasks'])}
팁: {calendar['tips']}
""")
    
    # 3. 토양 관리
    if any(word in question_lower for word in ["토양", "흙", "땅", "비료", "ph"]):
        soil = get_soil_recommendations()
        context_parts.append(f"\n=== 토양 관리 ===\n{soil}\n")
    
    # 4. 병해충 정보
    if any(word in question_lower for word in ["병", "해충", "벌레", "방제", "약", "병해충", "응애", "깍지"]):
        pests = get_pest_alerts()
        context_parts.append(f"""
=== 병해충 정보 ===
주의 병해충: {', '.join(pests['high_risk'])}
예방 조치: {pests['prevention']}
""")
    
    return "\n".join(context_parts) if context_parts else ""


# ============================================
# ROUTES
# ============================================

@app.route("/")
def home():
    return render_template("index_improved.html")


@app.route("/ask", methods=["POST"])
def ask():
    try:
        data = request.get_json()
        question = data.get("question")
        region = data.get("region", "제주")  # 기본값: 제주

        if not question or not question.strip():
            return jsonify({"answer": "질문을 입력해주세요."}), 400

        # 실시간 API 데이터로 컨텍스트 구성
        api_context = build_context_for_llm(question, region)
        
        # LLM 호출
        answer = call_llm(question, api_context)
        return jsonify({"answer": answer})
    
    except Exception as e:
        print(f"Error in /ask route: {str(e)}")
        return jsonify({"answer": "죄송합니다. 오류가 발생했습니다. 다시 시도해주세요."}), 500


@app.route("/api/regions", methods=["GET"])
def get_regions():
    """사용 가능한 지역 목록 반환"""
    return jsonify({
        "regions": list(SHORT_FORECAST_COORDS.keys())
    })


@app.route("/api/weather/<region>", methods=["GET"])
def get_weather(region):
    """특정 지역 날씨 조회"""
    try:
        weather = get_weather_for_context(region)
        return jsonify({"weather": weather})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================
# LLM CALL
# ============================================

def call_llm(prompt, api_context=""):
    url = LINK
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:5000",
        "X-Title": "Jeju Farmer AI"
    }

    system_content = f"""너는 제주도의 농민들을 돕는 친절한 AI 농업 전문가다. 
제주도의 기후와 토양 특성을 고려하여 조언해라.
귤 농사, 밭농사, 토양 관리, 병해충 방제, 비료 사용 등에 대해 실용적이고 구체적인 답변을 제공해라.
항상 자연스러운 한국어로 대답하고, 농민들이 쉽게 이해할 수 있도록 어려운 전문 용어는 피하거나 쉽게 풀어서 설명해라.
답변은 친근하고 따뜻한 어조로, 존댓말을 사용해라.

[CHATTEEN_AI_IDENTITY]
너의 이름은 귤담 AI(Gyuldam AI) 이다.
귤담 AI(Gyuldam AI)는 학생 주도의 농업 지원 프로젝트인 틴저린 프로젝트 (Teengerine Project)가 개발한 AI 도우미이다.
정보 제공과 설명을 돕는 역할에 집중한다.

[TEENGERINE_PROJECT_CONTEXT]
틴저린 프로젝트 (Teengerine Project)는 학생들이 제주 지역 농가를 직접 방문해 현장 농작업을 돕고 SNS 운영을 통해 F2T 판매를 지원하는 프로젝트이다.
현재 약 10개 농가와 함께 운영되고 있습니다.

중요한 원칙:
- 사용자가 묻지 않으면 프로젝트를 먼저 언급하지 마세요.
- 자신을 운영 주체처럼 표현하지 마세요.
- 농가 입장에서 도움이 되는 정보를 중심으로 설명하세요.

아래는 실시간 기상 정보와 농사 정보입니다. 답변할 때 이 정보를 자연스럽게 활용하세요:
{api_context}

위 정보를 자연스럽게 답변에 녹여서 활용하되, 사용자가 물어보지 않은 정보는 강제로 언급하지 마세요."""

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_content},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 2000
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"]

    except requests.exceptions.Timeout:
        return "응답 시간이 초과되었습니다. 다시 시도해주세요."
    except requests.exceptions.RequestException as e:
        print(f"API Request Error: {str(e)}")
        return "AI 서비스에 연결할 수 없습니다. 잠시 후 다시 시도해주세요."
    except KeyError as e:
        print(f"Response parsing error: {str(e)}")
        return "응답을 처리하는 중 오류가 발생했습니다."
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return f"오류가 발생했습니다: {str(e)}"


if __name__ == "__main__":
    print("=" * 50)
    print("제주 농민 AI 도우미 시작")
    print("=" * 50)
    print("\n⚠️  중요: 기상청 API 키를 설정하세요!")
    print("   1. https://www.data.go.kr/ 에서 회원가입")
    print("   2. '기상청_단기예보 조회서비스' API 신청")
    print("   3. app.py 파일의 KMA_API_KEY에 키 입력")
    print("\n서버 시작 중...\n")
    
    ###app.run(debug=True, host='0.0.0.0', port=5000)
    app.run()
