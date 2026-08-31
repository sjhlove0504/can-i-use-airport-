import urllib.request
import re
import streamlit as st

# 페이지 레이아웃 및 타이틀 설정
st.set_page_config(page_title="주요 공항 착륙 가능 여부 판정기", page_icon="✈️", layout="centered")

st.title("✈️ 실시간 공항 기상 및 착륙 가능 여부")
st.caption("주요 공항별 METAR 정보 기반 저시정 및 운고 자동 판단 시스템")

# 1. 공항별 세부 착륙 최저 기준 설정
AIRPORTS = {
    "인천국제공항": {"icao": "RKSI", "min_rvr": 75, "min_ceiling": 200, "min_vis": 800},
    "김포국제공항": {"icao": "RKSS", "min_rvr": 175, "min_ceiling": 200, "min_vis": 800},
    "제주국제공항": {"icao": "RKPC", "min_rvr": 300, "min_ceiling": 200, "min_vis": 800},
    "김해국제공항": {"icao": "RKPK", "min_rvr": 550, "min_ceiling": 200, "min_vis": 800}
}

if "selected_airport" not in st.session_state:
    st.session_state.selected_airport = "인천국제공항"

# 2. 상단 버튼형 공항 선택 UI
st.write("### 📍 분석할 공항을 선택하세요")
cols = st.columns(len(AIRPORTS))
for i, name in enumerate(AIRPORTS.keys()):
    if cols[i].button(name, use_container_width=True):
        st.session_state.selected_airport = name

current_name = st.session_state.selected_airport
info = AIRPORTS[current_name]
icao_code = info["icao"]

st.divider()
st.subheader(f"🏢 {current_name} ({icao_code}) 기상 분석")

# METAR 데이터 직접 파싱 함수 (avwx 없이 작동)
def parse_metar_raw(raw):
    # 시정 추출
    vis = None
    vis_match = re.search(r'\b(\d{4})\b', raw)
    if vis_match and vis_match.group(1) != icao_code:
        vis = int(vis_match.group(1))

    # RVR 추출
    rvr_list = re.findall(r'R\d{2}[LCR]?/([MP]?\d{4})', raw)
    lowest_rvr = None
    if rvr_list:
        clean_rvrs = [int(r.replace('M', '').replace('P', '')) for r in rvr_list]
        lowest_rvr = min(clean_rvrs)

    # 운고(Ceiling - BKN, OVC 최저층) 추출
    ceiling_ft = None
    cloud_matches = re.findall(r'(BKN|OVC)(\d{3})', raw)
    if cloud_matches:
        heights = [int(h) * 100 for _, h in cloud_matches]
        ceiling_ft = min(heights)

    return vis, lowest_rvr, ceiling_ft

def get_metar_data(icao):
    try:
        url = f"https://tgftp.nws.noaa.gov/data/observations/metar/stations/{icao.upper()}.TXT"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            lines = response.read().decode('utf-8').splitlines()
            raw_metar = lines[1] if len(lines) > 1 else lines[0]
            return raw_metar
    except Exception as e:
        st.error(f"기상 정보를 불러오는데 실패했습니다: {e}")
        return None

with st.spinner(f"{current_name} 기상 데이터를 수집 중입니다..."):
    raw_metar = get_metar_data(icao_code)

if raw_metar:
    st.write("**📄 METAR 원문**")
    st.code(raw_metar, language="text")

    current_vis, lowest_rvr, ceiling_ft = parse_metar_raw(raw_metar)

    target_rvr = info["min_rvr"]
    target_vis = info["min_vis"]
    target_ceiling = info["min_ceiling"]

    st.subheader("📊 실시간 관측 수치 vs 최저 기준치")
    m1, m2, m3 = st.columns(3)
    
    with m1:
        if current_vis is not None:
            vis_status = "양호" if current_vis >= target_vis else "미달"
            m1.metric("지상 시정 (VIS)", f"{current_vis} m", f"기준: {target_vis}m | 상태: {vis_status}")
        else:
            m1.metric("지상 시정 (VIS)", "정보 없음", f"기준: {target_vis}m")

    with m2:
        if lowest_rvr is not None:
            rvr_status = "양호" if lowest_rvr >= target_rvr else "미달"
            m2.metric("최저 RVR", f"{lowest_rvr} m", f"기준: {target_rvr}m | 상태: {rvr_status}")
        else:
            m2.metric("최저 RVR", "미관측 (양호)", f"최저 기준: {target_rvr}m")

    with m3:
        if ceiling_ft is not None:
            ceil_status = "양호" if ceiling_ft >= target_ceiling else "미달"
            m3.metric("운고 (Ceiling)", f"{ceiling_ft} ft", f"기준: {target_ceiling}ft | 상태: {ceil_status}")
        else:
            m3.metric("운고 (Ceiling)", "운고 없음 (양호)", f"최저 기준: {target_ceiling}ft")

    st.divider()
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
