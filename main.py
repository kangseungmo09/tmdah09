import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path
import unicodedata
import io

# 1. 페이지 설정
st.set_page_config(page_title="🌱 극지식물 최적 EC 농도 연구", layout="wide")

# 한글 폰트 깨짐 방지 CSS
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@100;400;700&display=swap');
html, body, [class*="css"], .stMarkdown {
    font-family: 'Noto Sans KR', 'Malgun Gothic', sans-serif;
}
</style>
""", unsafe_allow_html=True)

# 2. 데이터 로딩 및 파일명 정규화 처리
@st.cache_data
def load_data():
    base_path = Path("data")
    if not base_path.exists():
        st.error(f"❌ '{base_path}' 폴더를 찾을 수 없습니다.")
        return None, None

    # 파일명 NFC/NFD 하이브리드 매칭 함수
    def find_file(directory, target_name):
        for p in directory.iterdir():
            norm_p = unicodedata.normalize('NFC', p.name)
            norm_target = unicodedata.normalize('NFC', target_name)
            if norm_p == norm_target:
                return p
        return None

    # 학교 정보 정의
    schools = {
        "송도고": {"ec": 1.0, "color": "#1f77b4"},
        "하늘고": {"ec": 2.0, "color": "#2ca02c"}, # 최적
        "아라고": {"ec": 4.0, "color": "#ff7f0e"},
        "동산고": {"ec": 8.0, "color": "#d62728"}
    }

    env_data = {}
    growth_data = {}

    # 환경 데이터 로드
    for school in schools.keys():
        file_path = find_file(base_path, f"{school}_환경데이터.csv")
        if file_path:
            df = pd.read_csv(file_path)
            df['time'] = pd.to_datetime(df['time'])
            df['school'] = school
            env_data[school] = df

    # 생육 결과 데이터 로드 (XLSX)
    growth_file_path = find_file(base_path, "4개교_생육결과데이터.xlsx")
    if growth_file_path:
        xl = pd.ExcelFile(growth_file_path)
        # 시트명도 NFC 정규화하여 매칭
        for sheet in xl.sheet_names:
            norm_sheet = unicodedata.normalize('NFC', sheet)
            if norm_sheet in schools:
                df = pd.read_excel(growth_file_path, sheet_name=sheet)
                df['school'] = norm_sheet
                growth_data[norm_sheet] = df

    return env_data, growth_data, schools

with st.spinner('데이터를 불러오는 중입니다...'):
    env_dict, growth_dict, school_info = load_data()

if not env_dict or not growth_dict:
    st.stop()

# 데이터 통합
all_env = pd.concat(env_dict.values(), ignore_index=True)
all_growth = pd.concat(growth_dict.values(), ignore_index=True)

# 3. 사이드바
st.sidebar.title("🌲 설정")
selected_school = st.sidebar.selectbox(
    "분석 대상 학교 선택",
    ["전체"] + list(school_info.keys())
)

# 4. 메인 화면 제목
st.title("🌱 극지식물 최적 EC 농도 연구 대시보드")
st.markdown("---")

tab1, tab2, tab3 = st.tabs(["📖 실험 개요", "🌡️ 환경 데이터", "📊 생육 결과"])

# --- Tab 1: 실험 개요 ---
with tab1:
    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("연구 배경 및 목적")
        st.info("""
        본 연구는 극지 환경에서 서식하는 식물의 생산성을 극대화하기 위한 **최적 EC(전기전도도) 농도**를 규명하는 것을 목적으로 합니다.
        각 학교별로 서로 다른 EC 조건을 설정하여 생육 데이터를 수집하고 비교 분석을 수행하였습니다.
        """)
        
        # 학교별 EC 조건 표
        st.subheader("학교별 실험 조건")
        cond_data = []
        for name, info in school_info.items():
            cond_data.append({
                "학교명": name,
                "EC 목표 (dS/m)": info['ec'],
                "개체수": len(growth_dict.get(name, [])),
                "상태": "최적" if name == "하늘고" else "실험군"
            })
        st.table(pd.DataFrame(cond_data))

    with col2:
        st.subheader("핵심 지표")
        st.metric("총 개체수", f"{len(all_growth)} 개체")
        st.metric("평균 온도", f"{all_env['temperature'].mean():.1f} °C")
        st.metric("평균 습도", f"{all_env['humidity'].mean():.1f} %")
        st.success("최적 EC: 2.0 dS/m (하늘고)")

# --- Tab 2: 환경 데이터 ---
with tab2:
    st.subheader("학교별 환경 지표 비교")
    
    # 2x2 환경 비교 그래프
    env_avg = all_env.groupby('school').mean().reset_index()
    fig_env = make_subplots(rows=2, cols=2, subplot_titles=("평균 온도 (°C)", "평균 습도 (%)", "평균 pH", "목표 EC vs 실측 EC"))

    fig_env.add_trace(go.Bar(x=env_avg['school'], y=env_avg['temperature'], name="온도"), row=1, col=1)
    fig_env.add_trace(go.Bar(x=env_avg['school'], y=env_avg['humidity'], name="습도"), row=1, col=2)
    fig_env.add_trace(go.Bar(x=env_avg['school'], y=env_avg['ph'], name="pH"), row=2, col=1)
    
    # 목표 vs 실측 EC
    target_ecs = [school_info[s]['ec'] for s in env_avg['school']]
    fig_env.add_trace(go.Bar(x=env_avg['school'], y=target_ecs, name="목표 EC"), row=2, col=2)
    fig_env.add_trace(go.Bar(x=env_avg['school'], y=env_avg['ec'], name="실측 EC"), row=2, col=2)

    fig_env.update_layout(height=600, showlegend=False, font=dict(family="Malgun Gothic, Apple SD Gothic Neo, sans-serif"))
    st.plotly_chart(fig_env, use_container_width=True)

    # 시계열 분석
    if selected_school != "전체":
        st.subheader(f"📈 {selected_school} 실시간 환경 변화")
        school_df = env_dict[selected_school].sort_values('time')
        
        # 온도/습도 시계열
        fig_line = px.line(school_df, x='time', y=['temperature', 'humidity'], title="온도 및 습도 변화")
        st.plotly_chart(fig_line, use_container_width=True)
        
        # EC 시계열 + 목표 수평선
        fig_ec = px.line(school_df, x='time', y='ec', title="EC 변화 및 목표치")
        fig_ec.add_hline(y=school_info[selected_school]['ec'], line_dash="dash", line_color="red", annotation_text="목표 EC")
        st.plotly_chart(fig_ec, use_container_width=True)
        
        with st.expander(f"{selected_school} 환경 데이터 원본 보기"):
            st.dataframe(school_df)
            csv = school_df.to_csv(index=False).encode('utf-8-sig')
            st.download_button("CSV 다운로드", data=csv, file_name=f"{selected_school}_env.csv", mime='text/csv')

# --- Tab 3: 생육 결과 ---
with tab3:
    # 핵심 결과 카드
    growth_avg = all_growth.groupby('school').mean(numeric_only=True).reset_index()
    # EC 정보 결합
    growth_avg['target_ec'] = growth_avg['school'].map(lambda x: school_info[x]['ec'])
    growth_avg = growth_avg.sort_values('target_ec')

    max_weight_school = growth_avg.loc[growth_avg['생중량(g)'].idxmax(), 'school']
    
    st.info(f"🥇 **분석 결과:** 평균 생중량이 가장 높은 학교는 **{max_weight_school}**이며, 해당 조건의 EC는 **{school_info[max_weight_school]['ec']} dS/m**입니다.")

    # 2x2 생육 지표 그래프
    fig_growth = make_subplots(rows=2, cols=2, subplot_titles=("평균 생중량 (g)", "평균 잎 수 (장)", "평균 지상부 길이 (mm)", "학교별 개체수"))
    
    # 생중량 강조 (최적값 색상 변경)
    colors = ['lightslash' if s != max_weight_school else 'royalblue' for s in growth_avg['school']]
    
    fig_growth.add_trace(go.Bar(x=growth_avg['school'], y=growth_avg['생중량(g)'], marker_color=colors), row=1, col=1)
    fig_growth.add_trace(go.Bar(x=growth_avg['school'], y=growth_avg['잎 수(장)']), row=1, col=2)
    fig_growth.add_trace(go.Bar(x=growth_avg['school'], y=growth_avg['지상부 길이(mm)']), row=2, col=1)
    
    counts = all_growth['school'].value_counts().reindex(growth_avg['school'])
    fig_growth.add_trace(go.Bar(x=counts.index, y=counts.values), row=2, col=2)

    fig_growth.update_layout(height=700, showlegend=False, font=dict(family="Malgun Gothic, Apple SD Gothic Neo, sans-serif"))
    st.plotly_chart(fig_growth, use_container_width=True)

    # 분포 분석 (Box plot)
    st.subheader("생중량 분포 비교")
    fig_box = px.box(all_growth, x="school", y="생중량(g)", color="school", points="all")
    st.plotly_chart(fig_box, use_container_width=True)

    # 상관관계
    col_corr1, col_corr2 = st.columns(2)
    with col_corr1:
        st.plotly_chart(px.scatter(all_growth, x="잎 수(장)", y="생중량(g)", color="school", title="잎 수 vs 생중량"), use_container_width=True)
    with col_corr2:
        st.plotly_chart(px.scatter(all_growth, x="지상부 길이(mm)", y="생중량(g)", color="school", title="지상부 길이 vs 생중량"), use_container_width=True)

    # 데이터 다운로드 (BytesIO 사용)
    with st.expander("생육 데이터 원본 및 다운로드"):
        st.dataframe(all_growth)
        
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            all_growth.to_excel(writer, index=False, sheet_name='통합데이터')
            for sch, df in growth_dict.items():
                df.to_excel(writer, index=False, sheet_name=sch)
        
        st.download_button(
            label="XLSX 통합본 다운로드",
            data=buffer.getvalue(),
            file_name="극지식물_생육결과_종합.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
