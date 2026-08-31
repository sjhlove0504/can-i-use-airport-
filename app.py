import urllib.request
import streamlit as st
import avwx

# 페이지 레이아웃 및 타이틀 설정
st.set_page_config(page_title="주요 공항 착륙 가능 여부 판정기", page_icon="✈️", layout="centered")

st.title("✈️ 실시간 공항 기상 및 착륙 가능 여부")
st.caption("주요 공항별 METAR 정보 기반 저시정 및 운고 자동 판단 시스템")

# 1. 공항별 세부 착륙 최저 기준 설정 (CAT 등급 기준)
AIRPORTS = {
    "인천국제공항": {
        "icao": "RKSI",
        "min_rvr": 75,      # CAT IIIb 최저 RVR (75m)
        "min_ceiling": 200,  # CAT I DH (200ft)
        "min_vis": 800       # 기본 지상시정 최저치 (800m)
    },
    "김포국제공항": {
        "icao": "RKSS",
        "min_rvr": 175,     # CAT IIIa 최저 RVR (175m)
        "min_ceiling": 200,
        "min_vis": 800
    },
    "제주국제공항": {
        "icao": "RKPC",
        "min_rvr": 300,     # CAT II 최저 RVR (300m)
        "min_ceiling": 200,
        "min_vis": 800
    },
    "김해국제공항": {
        "icao": "RKPK",
        "min_rvr": 550,     # CAT I 최저 RVR (550m)
        "min_ceiling": 200,
        "min_vis": 800
    }
}

# 선택된 공항 상태 저장 (기본값: 인천국제공항)
if "selected_airport" not in st.session_state:
    st.session_state.selected_airport = "인천국제공항"

# 2. 상단 버튼형 공항 선택 UI
st.write("### 📍 분석할 공항을 선택하세요")
cols = st.columns(len(AIRPORTS))

for i, name in enumerate(AIRPORTS.keys()):
    if cols[i].button(name, use_container_width=True):
        st.session_state.selected_airport = name

# 현재 선택된 공항 정보 가져오기
current_name = st.session_state.selected_airport
info = AIRPORTS[current_name]
icao_code = info["icao"]

st.divider()
st.subheader(f"🏢 {current_name} ({icao_code}) 기상 분석")

# NOAA 직접 수집형 기상 불러오기 함수
def get_metar_data(icao):
    try:
        url = f"https://tgftp.nws.noaa.gov/data/observations/metar/stations/{icao.upper()}.TXT"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        
        with urllib.request.urlopen(req, timeout=5) as response:
            lines = response.read().decode('utf-8').splitlines()
            raw_metar = lines[1] if len(lines) > 1 else lines[0]
            
        metar = avwx.Metar(icao)
        metar.parse(raw_metar)
        return metar
    except Exception as e:
        st.error(f"기상 정보를 불러오는데 실패했습니다: {e}")
        return None

# 데이터 수집 실행
with st.spinner(f"{current_name} 기상 데이터를 수집 중입니다..."):
    metar = get_metar_data(icao_code)

if metar and metar.data:
    data = metar.data
    
    # METAR 원문 표시
    st.write("**📄 METAR 원문**")
    st.code(metar.raw, language="text")

    # 핵심 수치 추출
    current_vis = data.visibility.value if data.visibility else None
    
    lowest_rvr = None
    if data.runway_visibility:
        rvr_values = [r.min_visibility.value for r in data.runway_visibility if r.min_visibility]
        if rvr_values:
            lowest_rvr = min(rvr_values)

    ceiling_ft = None
    if data.clouds:
        for cloud in data.clouds:
            if cloud.type in ["BKN", "OVC"] and cloud.base is not None:
                ceiling_ft = cloud.base * 100
                break

    # 공항별 최저 기준치 불러오기
    target_rvr = info["min_rvr"]
    target_vis = info["min_vis"]
    target_ceiling = info["min_ceiling"]

    # 3. 수치 및 기준치 대조 시각화 (요청 사항 반영)
    st.subheader("📊 실시간 관측 수치 vs 최저 기준치")
    m1, m2, m3 = st.columns(3)
    
    # 지상 시정 (VIS) 표시
    with m1:
        if current_vis is not None:
            vis_status = "양호" if current_vis >= target_vis else "미달"
            m1.metric(
                label="지상 시정 (VIS)",
                value=f"{current_vis} m",
                delta=f"기준: {target_vis}m | 상태: {vis_status}",
                delta_color="normal" if vis_status == "양호" else "inverse"
            )
        else:
            m1.metric("지상 시정 (VIS)", "정보 없음", f"기준: {target_vis}m")

    # 활주로 가시범위 (RVR) 표시
    with m2:
        if lowest_rvr is not None:
            rvr_status = "양호" if lowest_rvr >= target_rvr else "미달"
            m2.metric(
                label="최저 RVR",
                value=f"{lowest_rvr} m",
                delta=f"기준: {target_rvr}m | 상태: {rvr_status}",
                delta_color="normal" if rvr_status == "양호" else "inverse"
            )
        else:
            m2.metric("최저 RVR", "미관측 (양호)", f"최저 기준: {target_rvr}m")

    # 운고 (Ceiling) 표시
    with m3:
        if ceiling_ft is not None:
            ceil_status = "양호" if ceiling_ft >= target_ceiling else "미달"
            m3.metric(
                label="운고 (Ceiling)",
                value=f"{ceiling_ft} ft",
                delta=f"기준: {target_ceiling}ft | 상태: {ceil_status}",
                delta_color="normal" if ceil_status == "양호" else "inverse"
            )
        else:
            m3.metric("운고 (Ceiling)", "운고 없음 (양호)", f"최저 기준: {target_ceiling}ft")

    st.divider()

    # 4. 종합 착륙 가능 여부 평가 결과 출력
    st.subheader("🛫 종합 착륙 가능 여부 평가")

    if lowest_rvr is not None:
        if lowest_rvr >= target_rvr:
            if ceiling_ft is not None and ceiling_ft < target_ceiling:
                st.warning(f"🟡 **주의 (운고 미달)**: RVR({lowest_rvr}m)은 기준({target_rvr}m)을 충족하지만, 운고({ceiling_ft}ft)가 기준({target_ceiling}ft) 미만입니다.")
            else:
                st.success(f"🟢 **착륙 가능**: RVR({lowest_rvr}m)과 운고 수치 모두 공항 최저 기준(RVR {target_rvr}m 이상)을 충족합니다.")
        else:
            st.error(f"🔴 **착륙 불가**: 현재 최저 RVR({lowest_rvr}m)이 {current_name} 착륙 최저 한계치({target_rvr}m) 미만입니다. 회항(Divert)을 고려해야 합니다.")
    else:
        vis_ok = current_vis is not None and current_vis >= target_vis
        ceiling_ok = ceiling_ft is None or ceiling_ft >= target_ceiling

        if vis_ok and ceiling_ok:
            st.success("🟢 **착륙 가능**: 시정 및 운고 관측치가 공항 접근 기준을 수월하게 충족합니다.")
        elif not vis_ok:
            st.error(f"🔴 **착륙 제한**: 지상 시정({current_vis}m)이 최소 기준치({target_vis}m) 미만입니다.")
        else:
            st.warning(f"🟡 **착륙 제한**: 운고({ceiling_ft}ft)가 최소 기준치({target_ceiling}ft) 미만입니다.")