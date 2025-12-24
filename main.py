import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path
import unicodedata
import io

# -----------------------------------------------------------------------------
# 1. 페이지 설정 & CSS (한글 폰트 적용)
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="극지식물 최적 EC 농도 연구",
    page_icon="🌱",
    layout="wide"
)

# Streamlit UI 한글 폰트 적용
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;700&display=swap');
html, body, [class*="css"] {
    font-family: 'Noto Sans KR', 'Malgun Gothic', sans-serif;
}
</style>
""", unsafe_allow_html=True)

PLOTLY_FONT = dict(family="Noto Sans KR, Malgun Gothic, sans-serif")

# -----------------------------------------------------------------------------
# 2. 데이터 로딩 (유연한 파일 찾기 로직 적용)
# -----------------------------------------------------------------------------
SCHOOL_CONFIG = {
    "송도고": {"ec": 1.0, "color": "#1f77b4"},
    "하늘고": {"ec": 2.0, "color": "#2ca02c"},
    "아라고": {"ec": 4.0, "color": "#ff7f0e"},
    "동산고": {"ec": 8.0, "color": "#d62728"},
}

def normalize_str(s: str) -> str:
    """NFC 정규화 (맥/윈도우 자소 분리 해결)"""
    return unicodedata.normalize('NFC', s) if s else ""

def find_file_fuzzy(base_dir: Path, keyword: str, extension: str) -> Path:
    """
    파일명에 'keyword'(예: 송도고)와 'extension'(예: .csv)이 
    모두 포함된 파일을 찾아서 반환. (이중 확장자 .csv.csv 해결용)
    """
    if not base_dir.exists():
        return None
    
    keyword_norm = normalize_str(keyword)
    
    for p in base_dir.iterdir():
        if p.is_file() and not p.name.startswith('~$'): # 임시 파일 제외
            p_name_norm = normalize_str(p.name)
            # 파일명에 키워드(학교명)가 있고, 확장자(.csv 등)도 포함되어 있으면 선택
            if keyword_norm in p_name_norm and extension in p_name_norm:
                return p
    return None

@st.cache_data
def load_data():
    data_dir = Path("data")
    
    # 1. 폴더 존재 확인
    if not data_dir.exists():
        st.error(f"❌ 'data' 폴더가 없습니다. 현재 위치: {Path.cwd()}")
        # 혹시 상위 폴더에 있을 경우를 대비해 한 번 더 체크 (Streamlit Cloud 대응)
        if Path("polar-plant-dashboard/data").exists():
            data_dir = Path("polar-plant-dashboard/data")
        else:
            return None, None

    # --- CSV 데이터 로딩 ---
    env_dfs = []
    
    # 학교별로 파일을 찾아서 로드
    for school in SCHOOL_CONFIG.keys():
        # "송도고" 가 들어있고 ".csv" 가 들어있는 파일 찾기 (csv.csv도 찾아짐)
        file_path = find_file_fuzzy(data_dir, school, ".csv")
        
        if file_path:
            try:
                df = pd.read_csv(file_path)
                df.columns = [c.strip().lower() for c in df.columns] # 컬럼 소문자 변환
                
                # 필수 컬럼 체크
                required = ['time', 'temperature', 'humidity', 'ph', 'ec']
                if all(c in df.columns for c in required):
                    df['school'] = school
                    df['target_ec'] = SCHOOL_CONFIG[school]['ec']
                    env_dfs.append(df)
            except Exception as e:
                st.warning(f"⚠️ {school} 파일({file_path.name}) 로드 중 오류: {e}")
        else:
            st.warning(f"⚠️ '{school}' 관련 .csv 파일을 찾을 수 없습니다.")

    env_df_total = pd.concat(env_dfs, ignore_index=True) if env_dfs else pd.DataFrame()
    if not env_df_total.empty and 'time' in env_df_total.columns:
        env_df_total['time'] = pd.to_datetime(env_df_total['time'], errors='coerce')

    # --- Excel 데이터 로딩 ---
    growth_dfs = []
    # "생육" 이라는 단어와 ".xlsx" 가 들어있는 파일 찾기 (xlsx.xlsx도 찾아짐)
    excel_path = find_file_fuzzy(data_dir, "생육", ".xlsx")
    
    if excel_path:
        try:
            xls = pd.ExcelFile(excel_path)
            sheet_map = {normalize_str(s): s for s in xls.sheet_names}
            
            for school in SCHOOL_CONFIG.keys():
                school_norm = normalize_str(school)
                
                # 시트 이름 매칭 확인
                matched_sheet = None
                for sheet_key in sheet_map.keys():
                    if school_norm in sheet_key: # 시트 이름에 학교명이 포함되면 OK
                        matched_sheet = sheet_map[sheet_key]
                        break
                
                if matched_sheet:
                    df_g = pd.read_excel(xls, sheet_name=matched_sheet)
                    df_g['school'] = school
                    df_g['target_ec'] = SCHOOL_CONFIG[school]['ec']
                    growth_dfs.append(df_g)
                else:
                    st.warning(f"⚠️ 엑셀 파일 내 '{school}' 시트를 찾을 수 없습니다.")
                    
        except Exception as e:
            st.warning(f"⚠️ 엑셀 파일({excel_path.name}) 로드 실패: {e}")
    else:
        st.warning("⚠️ '생육' 관련 .xlsx 파일을 찾을 수 없습니다.")

    growth_df_total = pd.concat(growth_dfs, ignore_index=True) if growth_dfs else pd.DataFrame()

    return env_df_total, growth_df_total

# -----------------------------------------------------------------------------
# 3. 메인 로직
# -----------------------------------------------------------------------------
def main():
    st.title("🌱 극지식물 최적 EC 농도 연구 대시보드")
    
    with st.spinner("데이터 파일을 검색하고 불러오는 중..."):
        env_df, growth_df = load_data()

    if (env_df is None or env_df.empty) and (growth_df is None or growth_df.empty):
        st.error("데이터를 불러오지 못했습니다. data 폴더 안의 파일명을 확인해주세요.")
        return

    # 사이드바
    st.sidebar.header("🔍 필터 옵션")
    school_list = ["전체"] + list(SCHOOL_CONFIG.keys())
    selected_school = st.sidebar.selectbox("학교 선택", school_list)

    if selected_school != "전체":
        env_filtered = env_df[env_df['school'] == selected_school] if not env_df.empty else pd.DataFrame()
        growth_filtered = growth_df[growth_df['school'] == selected_school] if not growth_df.empty else pd.DataFrame()
    else:
        env_filtered = env_df
        growth_filtered = growth_df

    tab1, tab2, tab3 = st.tabs(["📖 실험 개요", "🌡️ 환경 데이터", "📊 생육 결과"])

    # Tab 1: 개요
    with tab1:
        st.header("연구 개요")
        col1, col2 = st.columns([1, 2])
        with col1:
            st.subheader("실험 조건")
            summary = [{"학교": k, "목표 EC": v['ec']} for k, v in SCHOOL_CONFIG.items()]
            st.dataframe(pd.DataFrame(summary), hide_index=True, use_container_width=True)
        with col2:
            st.subheader("데이터 현황")
            if not growth_df.empty:
                cnt = len(growth_df)
                st.metric("총 생육 데이터 개수", f"{cnt}개")
            if not env_df.empty:
                last_update = env_df['time'].max()
                st.metric("환경 데이터 마지막 측정", str(last_update))

    # Tab 2: 환경 데이터
    with tab2:
        if not env_filtered.empty:
            st.subheader("환경 데이터 시계열 분석")
            
            # 그래프 2개 배치 (온도, EC)
            c1, c2 = st.columns(2)
            with c1:
                fig_t = px.line(env_filtered, x='time', y='temperature', color='school', title="온도 변화")
                fig_t.update_layout(font=PLOTLY_FONT)
                st.plotly_chart(fig_t, use_container_width=True)
            with c2:
                fig_e = px.line(env_filtered, x='time', y='ec', color='school', title="EC 변화")
                fig_e.update_layout(font=PLOTLY_FONT)
                st.plotly_chart(fig_e, use_container_width=True)

            with st.expander("환경 데이터 원본"):
                st.dataframe(env_filtered)
                # CSV 다운로드
                csv_buffer = env_filtered.to_csv(index=False).encode('utf-8-sig')
                st.download_button("CSV 다운로드", csv_buffer, "env_data.csv", "text/csv")
        else:
            st.info("표시할 환경 데이터가 없습니다.")

    # Tab 3: 생육 결과
    with tab3:
        if not growth_filtered.empty:
            st.subheader("EC별 생육 비교")
            
            # KPI 계산: 생중량 비교
            avg_weight = growth_filtered.groupby('school')['생중량(g)'].mean().reset_index()
            avg_weight['color'] = avg_weight['school'].map(lambda x: SCHOOL_CONFIG[x]['color'])
            
            fig_bar = px.bar(avg_weight, x='school', y='생중량(g)', color='school', 
                             title="학교별 평균 생중량", text_auto='.2f')
            fig_bar.update_layout(font=PLOTLY_FONT)
            st.plotly_chart(fig_bar, use_container_width=True)
            
            # 상관관계
            st.subheader("상관관계 분석")
            fig_scat = px.scatter(growth_filtered, x='잎 수(장)', y='생중량(g)', color='school',
                                  title="잎 수 vs 생중량", trendline='ols')
            fig_scat.update_layout(font=PLOTLY_FONT)
            st.plotly_chart(fig_scat, use_container_width=True)

            with st.expander("생육 데이터 원본"):
                st.dataframe(growth_filtered)
                # Excel 다운로드
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    growth_filtered.to_excel(writer, index=False)
                buffer.seek(0)
                st.download_button("Excel 다운로드", buffer, "growth_data.xlsx", 
                                   "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        else:
            st.info("표시할 생육 데이터가 없습니다.")

if __name__ == "__main__":
    main()
