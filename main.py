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
/* 탭 폰트 굵게 */
button[data-baseweb="tab"] {
    font-weight: 700;
}
</style>
""", unsafe_allow_html=True)

# Plotly 그래프용 한글 폰트 설정
PLOTLY_FONT = dict(family="Noto Sans KR, Malgun Gothic, sans-serif")

# -----------------------------------------------------------------------------
# 2. 데이터 로딩 및 전처리 (Unicode 정규화 포함)
# -----------------------------------------------------------------------------
SCHOOL_CONFIG = {
    "송도고": {"ec": 1.0, "color": "#1f77b4"},  # 파랑
    "하늘고": {"ec": 2.0, "color": "#2ca02c"},  # 초록 (최적)
    "아라고": {"ec": 4.0, "color": "#ff7f0e"},  # 주황
    "동산고": {"ec": 8.0, "color": "#d62728"},  # 빨강
}

def normalize_str(s: str) -> str:
    """NFC/NFD 정규화를 통해 문자열 비교 (Mac/Win 호환성 확보)"""
    return unicodedata.normalize('NFC', s)

def find_file_safe(base_dir: Path, target_name: str) -> Path:
    """디렉토리를 순회하며 정규화된 이름이 일치하는 파일 경로 반환"""
    target_norm = normalize_str(target_name)
    if not base_dir.exists():
        return None
    
    for p in base_dir.iterdir():
        if normalize_str(p.name) == target_norm:
            return p
    return None

@st.cache_data
def load_data():
    """데이터 로딩 함수 (캐싱 적용)"""
    data_dir = Path("data")
    if not data_dir.exists():
        st.error(f"❌ 'data' 폴더를 찾을 수 없습니다. 현재 경로: {Path.cwd()}")
        return None, None

    # --- 1. 환경 데이터 로딩 (CSV) ---
    env_dfs = []
    
    # 각 학교별 CSV 파일 매핑
    csv_files = {
        "송도고": "송도고_환경데이터.csv",
        "하늘고": "하늘고_환경데이터.csv",
        "아라고": "아라고_환경데이터.csv",
        "동산고": "동산고_환경데이터.csv"
    }

    for school, filename in csv_files.items():
        file_path = find_file_safe(data_dir, filename)
        if file_path:
            try:
                df = pd.read_csv(file_path)
                # 컬럼명 소문자 공백 제거 등 표준화가 필요하다면 여기서 수행
                df.columns = [c.strip().lower() for c in df.columns]
                
                # 필수 컬럼 확인 (time, temperature, humidity, ph, ec)
                required_cols = ['time', 'temperature', 'humidity', 'ph', 'ec']
                if all(c in df.columns for c in required_cols):
                    df['school'] = school
                    df['target_ec'] = SCHOOL_CONFIG[school]['ec']
                    env_dfs.append(df)
            except Exception as e:
                st.warning(f"⚠️ {school} 데이터 로드 실패: {e}")
    
    env_df_total = pd.concat(env_dfs, ignore_index=True) if env_dfs else pd.DataFrame()
    if not env_df_total.empty:
         # 시간 형식 변환 시도
        try:
            env_df_total['time'] = pd.to_datetime(env_df_total['time'])
        except:
            pass

    # --- 2. 생육 결과 데이터 로딩 (XLSX) ---
    growth_dfs = []
    excel_path = find_file_safe(data_dir, "4개교_생육결과데이터.xlsx")
    
    if excel_path:
        try:
            xls = pd.ExcelFile(excel_path)
            # 시트 이름도 정규화하여 매칭
            sheet_map = {normalize_str(s): s for s in xls.sheet_names}
            
            for school in SCHOOL_CONFIG.keys():
                school_norm = normalize_str(school)
                if school_norm in sheet_map:
                    real_sheet_name = sheet_map[school_norm]
                    df_g = pd.read_excel(xls, sheet_name=real_sheet_name)
                    df_g['school'] = school
                    df_g['target_ec'] = SCHOOL_CONFIG[school]['ec']
                    growth_dfs.append(df_g)
        except Exception as e:
            st.warning(f"⚠️ 엑셀 데이터 로드 실패: {e}")
            
    growth_df_total = pd.concat(growth_dfs, ignore_index=True) if growth_dfs else pd.DataFrame()

    return env_df_total, growth_df_total

# -----------------------------------------------------------------------------
# 3. 메인 로직 및 레이아웃
# -----------------------------------------------------------------------------

def main():
    st.title("🌱 극지식물 최적 EC 농도 연구 대시보드")
    
    with st.spinner("데이터를 불러오는 중입니다..."):
        env_df, growth_df = load_data()

    if env_df.empty and growth_df.empty:
        st.error("데이터를 로드할 수 없습니다. 'data' 폴더와 파일명을 확인해주세요.")
        return

    # --- 사이드바 ---
    st.sidebar.header("🔍 필터 옵션")
    school_list = ["전체"] + list(SCHOOL_CONFIG.keys())
    selected_school = st.sidebar.selectbox("학교 선택", school_list)

    # 필터링
    if selected_school != "전체":
        env_filtered = env_df[env_df['school'] == selected_school]
        growth_filtered = growth_df[growth_df['school'] == selected_school]
    else:
        env_filtered = env_df
        growth_filtered = growth_df

    # --- 탭 구성 ---
    tab1, tab2, tab3 = st.tabs(["📖 실험 개요", "🌡️ 환경 데이터", "📊 생육 결과"])

    # =========================================================================
    # Tab 1: 실험 개요
    # =========================================================================
    with tab1:
        st.header("연구 배경 및 목적")
        st.markdown("""
        > 본 연구는 극지식물의 생육에 미치는 **EC(전기전도도)**의 영향을 분석하여 
        > 스마트팜 환경에서의 **최적 배양액 농도**를 도출하는 것을 목적으로 합니다.
        """)
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.subheader("🏫 학교별 실험 조건")
            # 조건 요약 테이블 생성
            summary_data = []
            for sch, conf in SCHOOL_CONFIG.items():
                count = len(growth_df[growth_df['school'] == sch]) if not growth_df.empty else 0
                summary_data.append({
                    "학교명": sch,
                    "목표 EC (dS/m)": conf['ec'],
                    "실험 개체수": f"{count}개"
                })
            st.dataframe(pd.DataFrame(summary_data), hide_index=True, use_container_width=True)

        with col2:
            st.subheader("📌 주요 지표 (전체)")
            m1, m2, m3, m4 = st.columns(4)
            
            total_count = len(growth_df) if not growth_df.empty else 0
            avg_temp = env_df['temperature'].mean() if not env_df.empty else 0
            avg_hum = env_df['humidity'].mean() if not env_df.empty else 0
            
            m1.metric("총 개체수", f"{total_count:,}개")
            m2.metric("평균 온도", f"{avg_temp:.1f} °C")
            m3.metric("평균 습도", f"{avg_hum:.1f} %")
            m4.metric("최적 EC(가설)", "2.0 (하늘고)", delta="Target", delta_color="normal")

    # =========================================================================
    # Tab 2: 환경 데이터
    # =========================================================================
    with tab2:
        if env_df.empty:
            st.info("환경 데이터가 없습니다.")
        else:
            st.header("학교별 환경 데이터 비교")
            
            # --- 2x2 서브플롯 (평균 비교) ---
            # 학교별 평균 계산
            env_mean = env_df.groupby('school')[['temperature', 'humidity', 'ph', 'ec', 'target_ec']].mean().reset_index()
            
            # 순서 정렬 (EC 농도 순: 송도 -> 하늘 -> 아라 -> 동산)
            env_mean['sort_key'] = env_mean['school'].map(lambda x: SCHOOL_CONFIG[x]['ec'])
            env_mean = env_mean.sort_values('sort_key')

            fig_env = make_subplots(
                rows=2, cols=2,
                subplot_titles=("평균 온도 (°C)", "평균 습도 (%)", "평균 pH", "목표 EC vs 실측 EC"),
                vertical_spacing=0.15
            )

            # 색상 매핑 리스트 생성
            colors = [SCHOOL_CONFIG[s]['color'] for s in env_mean['school']]

            # 1. 온도
            fig_env.add_trace(go.Bar(
                x=env_mean['school'], y=env_mean['temperature'],
                name="온도", marker_color=colors, showlegend=False
            ), row=1, col=1)

            # 2. 습도
            fig_env.add_trace(go.Bar(
                x=env_mean['school'], y=env_mean['humidity'],
                name="습도", marker_color=colors, showlegend=False
            ), row=1, col=2)

            # 3. pH
            fig_env.add_trace(go.Bar(
                x=env_mean['school'], y=env_mean['ph'],
                name="pH", marker_color=colors, showlegend=False
            ), row=2, col=1)

            # 4. EC (이중 막대: 목표 vs 실측)
            fig_env.add_trace(go.Bar(
                x=env_mean['school'], y=env_mean['target_ec'],
                name="목표 EC", marker_color='lightgray', opacity=0.7
            ), row=2, col=2)
            
            fig_env.add_trace(go.Bar(
                x=env_mean['school'], y=env_mean['ec'],
                name="실측 EC", marker_color=colors
            ), row=2, col=2)

            fig_env.update_layout(height=600, font=PLOTLY_FONT)
            st.plotly_chart(fig_env, use_container_width=True)

            st.divider()

            # --- 시계열 분석 ---
            st.subheader(f"📈 시계열 변화 ({selected_school if selected_school != '전체' else '전체 학교'})")
            
            # 시계열용 데이터프레임 (전체면 전체, 선택이면 선택된 것)
            ts_df = env_filtered.sort_values('time')
            
            # 3개의 탭으로 시계열 분리 (너무 복잡해지지 않게)
            t_tab1, t_tab2, t_tab3 = st.tabs(["온도 변화", "습도 변화", "EC 변화"])
            
            color_map = {k: v['color'] for k, v in SCHOOL_CONFIG.items()}
            
            with t_tab1:
                fig_t = px.line(ts_df, x='time', y='temperature', color='school',
                                color_discrete_map=color_map, title="시간별 온도 변화")
                fig_t.update_layout(font=PLOTLY_FONT)
                st.plotly_chart(fig_t, use_container_width=True)
            
            with t_tab2:
                fig_h = px.line(ts_df, x='time', y='humidity', color='school',
                                color_discrete_map=color_map, title="시간별 습도 변화")
                fig_h.update_layout(font=PLOTLY_FONT)
                st.plotly_chart(fig_h, use_container_width=True)

            with t_tab3:
                fig_e = px.line(ts_df, x='time', y='ec', color='school',
                                color_discrete_map=color_map, title="시간별 EC 변화")
                # 목표 EC 라인 추가 (단일 학교 선택 시 명확함)
                if selected_school != "전체":
                    target = SCHOOL_CONFIG[selected_school]['ec']
                    fig_e.add_hline(y=target, line_dash="dash", line_color="red", 
                                    annotation_text=f"목표 EC {target}")
                fig_e.update_layout(font=PLOTLY_FONT)
                st.plotly_chart(fig_e, use_container_width=True)

            # --- 데이터 다운로드 ---
            with st.expander("💾 환경 데이터 원본 보기 및 다운로드"):
                st.dataframe(env_filtered)
                csv = env_filtered.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    label="CSV 다운로드",
                    data=csv,
                    file_name="environmental_data.csv",
                    mime="text/csv",
                )

    # =========================================================================
    # Tab 3: 생육 결과
    # =========================================================================
    with tab3:
        if growth_df.empty:
            st.info("생육 결과 데이터가 없습니다.")
        else:
            # 컬럼명 매핑 (사용자 편의) -> 실제 컬럼명 확인 필요하지만 제공된 정보 기반
            # 제공 컬럼: 개체번호, 잎 수(장), 지상부 길이(mm), 지하부길이(mm), 생중량(g)
            
            # 학교별 평균 생중량 계산 (최댓값 찾기용)
            g_mean = growth_df.groupby('school')['생중량(g)'].mean().sort_values(ascending=False)
            best_school = g_mean.index[0]
            max_weight = g_mean.iloc[0]

            st.header("🥇 핵심 결과: EC별 생육 비교")
            
            # KPI 카드
            kpi_cols = st.columns(1)
            kpi_cols[0].info(f"**최고 생중량 기록:** {best_school} (평균 {max_weight:.2f}g) — **EC {SCHOOL_CONFIG[best_school]['ec']} 조건**")

            # --- 2x2 서브플롯 (생육 지표) ---
            # 그룹핑
            growth_summary = growth_df.groupby('school').agg({
                '생중량(g)': 'mean',
                '잎 수(장)': 'mean',
                '지상부 길이(mm)': 'mean',
                '개체번호': 'count' # 개체수
            }).reset_index()
            
            # EC 순서 정렬
            growth_summary['ec'] = growth_summary['school'].map(lambda x: SCHOOL_CONFIG[x]['ec'])
            growth_summary = growth_summary.sort_values('ec')

            fig_growth = make_subplots(
                rows=2, cols=2,
                subplot_titles=("평균 생중량 (g) ⭐", "평균 잎 수 (장)", "평균 지상부 길이 (mm)", "실험 개체수 (n)"),
                vertical_spacing=0.15
            )

            g_colors = [SCHOOL_CONFIG[s]['color'] for s in growth_summary['school']]

            # 1. 생중량
            fig_growth.add_trace(go.Bar(
                x=growth_summary['school'], y=growth_summary['생중량(g)'],
                name="생중량", marker_color=g_colors, showlegend=False
            ), row=1, col=1)

            # 2. 잎 수
            fig_growth.add_trace(go.Bar(
                x=growth_summary['school'], y=growth_summary['잎 수(장)'],
                name="잎 수", marker_color=g_colors, showlegend=False
            ), row=1, col=2)

            # 3. 길이
            fig_growth.add_trace(go.Bar(
                x=growth_summary['school'], y=growth_summary['지상부 길이(mm)'],
                name="길이", marker_color=g_colors, showlegend=False
            ), row=2, col=1)

            # 4. 개체수
            fig_growth.add_trace(go.Bar(
                x=growth_summary['school'], y=growth_summary['개체번호'],
                name="개체수", marker_color='gray', showlegend=False
            ), row=2, col=2)

            fig_growth.update_layout(height=600, font=PLOTLY_FONT)
            st.plotly_chart(fig_growth, use_container_width=True)

            st.divider()

            col_a, col_b = st.columns(2)
            
            with col_a:
                st.subheader("📦 학교별 생중량 분포")
                # 전체 데이터를 이용한 박스플롯
                fig_box = px.box(growth_filtered, x='school', y='생중량(g)', color='school',
                                 color_discrete_map=color_map, points="all")
                fig_box.update_layout(font=PLOTLY_FONT)
                st.plotly_chart(fig_box, use_container_width=True)

            with col_b:
                st.subheader("🔗 상관관계 분석")
                corr_option = st.selectbox("X축 변수 선택", ["잎 수(장)", "지상부 길이(mm)"])
                fig_scatter = px.scatter(growth_filtered, x=corr_option, y='생중량(g)', 
                                         color='school', color_discrete_map=color_map,
                                         trendline="ols")
                fig_scatter.update_layout(font=PLOTLY_FONT)
                st.plotly_chart(fig_scatter, use_container_width=True)

            # --- 엑셀 다운로드 (BytesIO 사용) ---
            with st.expander("💾 생육 데이터 원본 보기 및 XLSX 다운로드"):
                st.dataframe(growth_filtered)
                
                # Excel 다운로드 로직
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    growth_filtered.to_excel(writer, index=False, sheet_name='Filtered_Data')
                
                buffer.seek(0)
                
                st.download_button(
                    label="Excel 다운로드",
                    data=buffer,
                    file_name="growth_data_filtered.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

if __name__ == "__main__":
    main()
