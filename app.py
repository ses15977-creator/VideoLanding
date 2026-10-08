import os
import cv2
import numpy as np
import tempfile
import time
import streamlit as st
from google import genai
from google.genai import types

# Streamlit 페이지 설정
st.set_page_config(
    page_title="비디오랜딩 (VideoLanding)", 
    page_icon="🎬", 
    layout="centered"
)

# 모바일 화면 최적화 CSS
st.markdown("""
    <style>
    .stApp {
        max-width: 100%;
        padding-left: 10px;
        padding-right: 10px;
    }
    [data-testid="stFileUploader"] {
        width: 100%;
    }
    .stButton button {
        width: 100%;
        height: 3em;
        font-weight: bold;
        border-radius: 8px;
    }
    </style>
""", unsafe_allow_html=True)

# --- 세션 상태 및 쿼리 파라미터(새로고침 유지) 초기화 ---
if "users_db" not in st.session_state:
    st.session_state.users_db = {"ses15977@gmail.com": "1234"}

if "saved_email" not in st.session_state:
    st.session_state.saved_email = ""

if "stored_files" not in st.session_state:
    st.session_state.stored_files = []

# URL 쿼리 파라미터에서 로그인 상태 확인 (새로고침 대응)
query_params = st.query_params
if "logged_in_user" in query_params:
    st.session_state.logged_in = True
    st.session_state.user_email = query_params["logged_in_user"]
else:
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if "user_email" not in st.session_state:
        st.session_state.user_email = ""

# --- 로그인 / 회원가입 화면 ---
if not st.session_state.logged_in:
    st.title("🔐 비디오랜딩 서비스")
    
    tab1, tab2 = st.tabs(["🔑 로그인", "📝 회원가입"])
    
    with tab1:
        st.markdown("등록된 이메일과 비밀번호로 로그인하세요.")
        login_email = st.text_input("이메일 주소", value=st.session_state.saved_email, key="login_email_input")
        login_pw = st.text_input("비밀번호", type="password", key="login_pw_input")
        remember_email = st.checkbox("이메일 주소 기억하기", value=bool(st.session_state.saved_email))
        
        if st.button("로그인", type="primary", key="login_submit_btn"):
            if login_email in st.session_state.users_db and st.session_state.users_db[login_email] == login_pw:
                st.session_state.logged_in = True
                st.session_state.user_email = login_email
                st.query_params["logged_in_user"] = login_email
                
                if remember_email:
                    st.session_state.saved_email = login_email
                else:
                    st.session_state.saved_email = ""
                    
                st.success("로그인 성공!")
                st.rerun()
            else:
                st.error("⚠️ 이메일 또는 비밀번호가 일치하지 않습니다.")
                    
    with tab2:
        st.markdown("새로운 계정을 등록하여 나만의 공간을 만드세요.")
        signup_email = st.text_input("사용할 이메일 주소", key="signup_email_input")
        signup_pw = st.text_input("사용할 비밀번호", type="password", key="signup_pw_input")
        
        if st.button("회원가입 완료", type="primary", key="signup_submit_btn"):
            if not signup_email or "@" not in signup_email:
                st.error("⚠️ 올바른 이메일 주소를 입력해주세요.")
            elif not signup_pw:
                st.error("⚠️ 비밀번호를 입력해주세요.")
            elif signup_email in st.session_state.users_db:
                st.warning("⚠️ 이미 가입된 이메일입니다. 로그인해 주세요.")
            else:
                st.session_state.users_db[signup_email] = signup_pw
                st.success("🎉 회원가입이 완료되었습니다! '로그인' 탭에서 로그인해 주세요.")

else:
    # --- 로그인 완료 후 메인 서비스 화면 ---
    user_email = st.session_state.user_email
    user_name = user_email.split('@')[0]

    st.sidebar.markdown(f"👤 **접속 계정:**\n`{user_email}`")
    
    if st.sidebar.button("로그아웃"):
        st.session_state.logged_in = False
        st.session_state.user_email = ""
        st.session_state.stored_files = []
        if "logged_in_user" in st.query_params:
            del st.query_params["logged_in_user"]
        st.rerun()

    st.sidebar.divider()
    st.sidebar.header("⚙️ 설정")
    
    if "gemini_api_key" not in st.session_state:
        st.session_state.gemini_api_key = os.environ.get("GEMINI_API_KEY", "")

    api_key_input = st.sidebar.text_input(
        "Gemini API Key 입력", 
        type="password", 
        value=st.session_state.gemini_api_key,
        key="api_key_text_input"
    )
    if api_key_input:
        st.session_state.gemini_api_key = api_key_input

    st.title("🎬 비디오랜딩 (VideoLanding)")
    st.markdown(f"환영합니다, **{user_name}**님! 영상 클립을 업로드하고 리스트 관리와 AI 분석을 이용해 보세요.")

    # 파일 업로드 컴포넌트
    uploaded_files = st.file_uploader(
        "정리할 영상 파일을 여러 개 선택하세요 (mp4, mov, avi)", 
        type=["mp4", "mov", "avi"], 
        accept_multiple_files=True
    )

    if uploaded_files:
        current_file_names = [f.name for f in st.session_state.stored_files]
        for uf in uploaded_files:
            if uf.name not in current_file_names:
                st.session_state.stored_files.append(uf)

    # --- 🎥 업로드된 영상 리스트 관리 및 개별 삭제, 미리보기 섹션 ---
    if st.session_state.stored_files:
        st.divider()
        st.subheader("📁 업로드된 영상 클립 관리")
        st.markdown("등록된 영상 목록을 확인하고, 불필요한 영상은 삭제하거나 선택하여 미리 재생해 보세요.")

        files_to_keep = []
        for idx, file_obj in enumerate(st.session_state.stored_files):
            col_info, col_del = st.columns([4, 1])
            with col_info:
                st.text(f"🎬 {file_obj.name}")
            with col_del:
                if st.button("삭제", key=f"del_btn_{idx}_{file_obj.name}"):
                    continue 
            files_to_keep.append(file_obj)
        
        if len(files_to_keep) != len(st.session_state.stored_files):
            st.session_state.stored_files = files_to_keep
            st.rerun()

        if st.session_state.stored_files:
            st.markdown("---")
            st.subheader("📺 영상 미리보기 플레이어")
            file_dict = {file.name: file for file in st.session_state.stored_files}
            selected_file_name = st.selectbox("재생할 영상을 선택하세요:", list(file_dict.keys()), key="preview_selectbox")

            if selected_file_name:
                st.video(file_dict[selected_file_name])

    def analyze_and_filter_video(video_path, blur_threshold=100.0, frame_interval=30):
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return {"error": "영상을 열 수 없습니다."}

        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps if fps > 0 else 0

        frame_count = 0
        blur_scores = []
        extracted_frames = []

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            if frame_count % frame_interval == 0:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                # 라플라시안 분산을 안전하게 계산 (OpenCV 표준 방식)
                laplacian = cv2.Laplacian(gray, cv2.CV_64F)
                blur_score = laplacian.var()
                blur_scores.append(blur_score)

                small_frame = cv2.resize(frame, (384, 384))
                extracted_frames.append(small_frame)

            frame_count += 1

        cap.release()

        avg_blur_score = np.mean(blur_scores) if blur_scores else 0
        is_blurry = avg_blur_score < blur_threshold

        return {
            "file_path": video_path,
            "file_name": os.path.basename(video_path),
            "duration": duration,
            "avg_blur_score": avg_blur_score,
            "is_blurry": is_blurry,
            "frames": extracted_frames[:3]
        }

    def ai_organize_videos_with_gemini(valid_videos, api_key):
        """Gemini 모델을 이용한 영상 내용 요약 및 편집 순서 정렬"""
        try:
