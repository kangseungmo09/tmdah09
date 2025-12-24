import streamlit as st
import pandas as pd
import plotly.express as px
from plotly.subplots import make_subplots
import io
import os
from pathlib import Path
import unicodedata

# 한글 폰트 설정
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR&display=swap');
html, body, [class*="css"] {
    font-family: 'Noto Sans KR', 'Malgun Gothic', sans-serif;
}
</style>
""", unsafe_allow_html=True)

# 데이터 파일 경로 처리
def get_data_files(folder_path):
    folder = Path(folder_path)
    files = [file for file in folder.iterdir() if unicodedata.normalize("NFC", file.name) == file.name]
    return files

# 데이터 로딩 함수
@st.cache_data
def load_data():
    # 환경 데이터 파일 로딩
    env_data_files = get_data_files("data/")
    env_data = {}
    for file in env_data_files:
        if file.suffix == '.csv':
            school_name = file.stem
            env_data[school_name] = pd.read_csv(file)
    
    # 생육 데이터 로딩
    growth_data = pd.read_excel("data/4개교_생육결과데이터.xlsx", sheet_name=None)
    
    return env_data, growth_data

env_data, growth_data = load_data()

# 대시보드 제목
st.title("🌱 극지식물 최적 EC 농도 연구")

# 사이드바 학교 선택
school_options = ['전체', '송도고', '하늘고', '아라고', '동산고']
selected_school = st.sidebar.selectbox("학교 선택", school_options)

# Tab 1: 실험 개요
tab1, tab2, tab3 = st.tabs(["📖 실험 개요", "🌡️ 환경 데이터", "📊 생육 결과"])

with tab1:
    st.header("연구 배경 및 목적")
    st.write("""
    본 연구는 극지식물의 최적 EC 농도를 도출하기 위해 여러 학교에서 환경 데이터를 수집하고, 이를 바탕으로 각 학교의 생육 결과를 비교하는 연구입니다.
    """)
    
    # 학교별 EC 조건 표
    ec_data = {
        '학교명': ['송도고', '하늘고', '아라고', '동산고'],
        'EC 목표': [1.0, 2.0, 4.0, 8.0],
        '개체수': [29, 45, 106, 58],
        '색상': ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']
    }
    ec_df = pd.DataFrame(ec_data)
    st.write(ec_df)

    # 주요 지표 카드
    total_plants = sum([env_data[school].shape[0] for school in env_data]) if selected_school == '전체' else env_data[selected_school].shape[0]
    avg_temp = env_data[selected_school].temperature.mean() if selected_school != '전체' else pd.concat([env_data[school].temperature.mean() for school in env_data]).mean()
    avg_humidity = env_data[selected_school].humidity.mean() if selected_school != '전체' else pd.concat([env_data[school].humidity.mean() for school in env_data]).mean()
    optimal_ec = 2.0 if selected_school == '하늘고' else 4.0 if selected_school == '아라고' else 1.0 if selected_school == '송도고' else 8.0

    st.metric("총 개체수", total_plants)
    st.metric("평균 온도", f"{avg_temp:.2f} °C")
    st.metric("평균 습도", f"{avg_humidity:.2f} %")
    st.metric("최적 EC", optimal_ec)

with tab2:
    st.header("학교별 환경 평균 비교")

    fig = make_subplots(rows=2, cols=2)

    # 평균 온도 막대 그래프
    fig.add_trace(
        px.bar(x=list(env_data.keys()), y=[env_data[school].temperature.mean() for school in env_data]).data[0],
        row=1, col=1
    )
    # 평균 습도 막대 그래프
    fig.add_trace(
        px.bar(x=list(env_data.keys()), y=[env_data[school].humidity.mean() for school in env_data]).data[0],
        row=1, col=2
    )
    # 평균 pH 막대 그래프
    fig.add_trace(
        px.bar(x=list(env_data.keys()), y=[env_data[school].ph.mean() for school in env_data]).data[0],
        row=2, col=1
    )
    # 목표 EC vs 실측 EC 이중 막대 그래프
    fig.add_trace(
        px.bar(x=list(env_data.keys()), y=[env_data[school].ec.mean() for school in env_data], title="실측 EC").data[0],
        row=2, col=2
    )
    fig.add_trace(
        px.bar(x=list(env_data.keys()), y=[1.0, 2.0, 4.0, 8.0], title="목표 EC").data[0],
        row=2, col=2
    )

    fig.update_layout(height=800, width=800, title_text="환경 데이터 비교")
    st.plotly_chart(fig)

    st.expander("환경 데이터 원본").write(env_data[selected_school] if selected_school != '전체' else pd.concat(env_data.values()))

with tab3:
    st.header("EC별 생육 결과")

    # EC별 평균 생중량
    growth_fig = make_subplots(rows=2, cols=2)

    ec_values = [1.0, 2.0, 4.0, 8.0]
    avg_biomass = {ec: growth_data[school_name].loc[growth_data[school_name]["EC"] == ec, "생중량"].mean() for school_name in growth_data for ec in ec_values}

    # 생중량 막대그래프
    growth_fig.add_trace(
        px.bar(x=list(avg_biomass.keys()), y=list(avg_biomass.values()), title="EC별 평균 생중량").data[0],
        row=1, col=1
    )

    # 나머지 막대그래프는 유사하게 추가

    growth_fig.update_layout(height=800, width=800, title_text="생육 결과 비교")
    st.plotly_chart(growth_fig)

    st.expander("학교별 생육 데이터 원본").write(growth_data[selected_school])

# XLSX 다운로드
@st.cache_data
def get_growth_data_for_download():
    buffer = io.BytesIO()
    df = growth_data[selected_school] if selected_school != '전체' else pd.concat(growth_data.values())
    df.to_excel(buffer, index=False, engine="openpyxl")
    buffer.seek(0)
    return buffer

st.download_button(
    label="생육 결과 데이터 다운로드",
    data=get_growth_data_for_download(),
    file_name="생육결과데이터.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
