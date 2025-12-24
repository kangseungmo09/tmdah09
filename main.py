import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import io
import os
from pathlib import Path
import unicodedata

# 한글 폰트 깨짐 방지
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR&display=swap');
html, body, [class*="css"] {
    font-family: 'Noto Sans KR', 'Malgun Gothic', sans-serif;
}
</style>
""", unsafe_allow_html=True)

# 데이터 파일 경로
DATA_DIR = Path("data")

# 파일명 Unicode Normalization (NFC 사용)
def normalize_filename(filename):
    return unicodedata.normalize("NFC", filename)

# @st.cache_data로 데이터 로딩 최적화
@st.cache_data
def load_data():
    try:
        # 환경 데이터 파일들 불러오기
        env_files = [normalize_filename(f) for f in DATA_DIR.iterdir() if f.suffix == '.csv']
        env_data = {}
        for file in env_files:
            school_name = file.stem  # 파일명에서 학교 이름 추출
            env_data[school_name] = pd.read_csv(file)
        
        # 생육 결과 데이터 파일 불러오기 (엑셀)
        growth_data_file = normalize_filename(DATA_DIR / "4개교_생육결과데이터.xlsx")
        growth_data = pd.read_excel(growth_data_file, sheet_name=None)  # 모든 시트를 읽음

        return env_data, growth_data

    except Exception as e:
        st.error(f"데이터 로딩 중 오류가 발생했습니다: {e}")
        return None, None

# 데이터 로드
env_data, growth_data = load_data()

if not env_data or not growth_data:
    st.stop()  # 데이터가 로드되지 않으면 대시보드 실행 중지

# Streamlit 레이아웃 설정
st.set_page_config(page_title="극지식물 최적 EC 농도 연구", layout="wide")

# 사이드바 학교 선택
school = st.sidebar.selectbox("학교 선택", ["전체", "송도고", "하늘고", "아라고", "동산고"])

# Tab 1: 📖 실험 개요
with st.expander("📖 실험 개요"):
    st.write("""
    연구 배경 및 목적:
    - 극지식물의 최적 EC 농도를 연구하고, 각 학교별 환경 조건에 따른 생육 결과를 비교합니다.
    - 최적 EC 농도를 도출하여 생장에 미치는 영향을 분석합니다.
    """)

    # 학교별 EC 조건 표
    ec_conditions = {
        "송도고": {"EC 목표": 1.0, "개체수": len(growth_data["송도고"]), "색상": "blue"},
        "하늘고": {"EC 목표": 2.0, "개체수": len(growth_data["하늘고"]), "색상": "green"},
        "아라고": {"EC 목표": 4.0, "개체수": len(growth_data["아라고"]), "색상": "red"},
        "동산고": {"EC 목표": 8.0, "개체수": len(growth_data["동산고"]), "색상": "purple"},
    }
    
    ec_df = pd.DataFrame.from_dict(ec_conditions, orient="index")
    st.write(ec_df)
    
    # 주요 지표 카드
    total_plants = sum([len(growth_data[school]) for school in ec_conditions.keys() if school == "전체" or school == school])
    avg_temp = sum([env_data[school]["temperature"].mean() for school in ec_conditions.keys() if school == "전체" or school == school]) / len(env_data)
    avg_humidity = sum([env_data[school]["humidity"].mean() for school in ec_conditions.keys() if school == "전체" or school == school]) / len(env_data)
    optimal_ec = ec_conditions[school]["EC 목표"] if school != "전체" else "각 학교별 EC 농도 확인"

    st.metric("총 개체수", total_plants)
    st.metric("평균 온도", avg_temp)
    st.metric("평균 습도", avg_humidity)
    st.metric("최적 EC", optimal_ec)


# Tab 2: 🌡️ 환경 데이터
with st.expander("🌡️ 환경 데이터"):
    fig = make_subplots(rows=2, cols=2, subplot_titles=["평균 온도", "평균 습도", "평균 pH", "목표 EC vs 실측 EC"])
    
    # 학교별 환경 평균 비교
    temp_data = [env_data[school]["temperature"].mean() for school in ec_conditions]
    humidity_data = [env_data[school]["humidity"].mean() for school in ec_conditions]
    ph_data = [env_data[school]["ph"].mean() for school in ec_conditions]
    ec_actual = [env_data[school]["ec"].mean() for school in ec_conditions]
    
    # 평균 온도 막대그래프
    fig.add_trace(go.Bar(x=list(ec_conditions.keys()), y=temp_data, name="평균 온도"), row=1, col=1)
    
    # 평균 습도 막대그래프
    fig.add_trace(go.Bar(x=list(ec_conditions.keys()), y=humidity_data, name="평균 습도"), row=1, col=2)
    
    # 평균 pH 막대그래프
    fig.add_trace(go.Bar(x=list(ec_conditions.keys()), y=ph_data, name="평균 pH"), row=2, col=1)
    
    # 목표 EC vs 실측 EC 비교
    fig.add_trace(go.Bar(x=list(ec_conditions.keys()), y=ec_actual, name="실측 EC", marker=dict(color="blue")), row=2, col=2)
    fig.add_trace(go.Scatter(x=list(ec_conditions.keys()), y=[ec_conditions[school]["EC 목표"] for school in ec_conditions], mode="lines", name="목표 EC", line=dict(color="red", dash="dash")), row=2, col=2)

    fig.update_layout(height=600, width=800, title_text="학교별 환경 평균 비교", font=dict(family="Malgun Gothic, Apple SD Gothic Neo, sans-serif"))
    st.plotly_chart(fig)

    # 선택한 학교 시계열
    if school != "전체":
        selected_school_data = env_data[school]
        st.line_chart(selected_school_data[['temperature', 'humidity', 'ec']].dropna())


# Tab 3: 📊 생육 결과
with st.expander("📊 생육 결과"):
    growth_df = growth_data[school]
    
    # 핵심 결과 카드: EC별 평균 생중량
    mean_weight_by_ec = {
        "송도고": growth_data["송도고"]["생중량(g)"].mean(),
        "하늘고": growth_data["하늘고"]["생중량(g)"].mean(),
        "아라고": growth_data["아라고"]["생중량(g)"].mean(),
        "동산고": growth_data["동산고"]["생중량(g)"].mean(),
    }
    
    optimal_ec = min(mean_weight_by_ec, key=mean_weight_by_ec.get)
    st.metric("최고 평균 생중량", mean_weight_by_ec[optimal_ec], help="최적 EC 농도에 해당하는 평균 생중량을 강조합니다.")
    
    # EC별 생육 비교
    fig2 = make_subplots(rows=2, cols=2, subplot_titles=["평균 생중량", "평균 잎 수", "평균 지상부 길이", "개체수 비교"])
    
    # 생중량 비교
    weight_data = [growth_data[school]["생중량(g)"].mean() for school in ec_conditions]
    fig2.add_trace(go.Bar(x=list(ec_conditions.keys()), y=weight_data, name="평균 생중량"), row=1, col=1)
    
    # 잎 수 비교
    leaf_count_data = [growth_data[school]["잎 수(장)"].mean() for school in ec_conditions]
    fig2.add_trace(go.Bar(x=list(ec_conditions.keys()), y=leaf_count_data, name="평균 잎 수"), row=1, col=2)
    
    # 지상부 길이 비교
    ground_length_data = [growth_data[school]["지상부 길이(mm)"].mean() for school in ec_conditions]
    fig2.add_trace(go.Bar(x=list(ec_conditions.keys()), y=ground_length_data, name="평균 지상부 길이"), row=2, col=1)
    
    # 개체수 비교
    count_data = [len(growth_data[school]) for school in ec_conditions]
    fig2.add_trace(go.Bar(x=list(ec_conditions.keys()), y=count_data, name="개체수"), row=2, col=2)
    
