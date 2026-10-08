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

if "saved_email" not in st.session_state:
    st.session_state.saved_email = ""

# --- 로그인 / 회원가입 화면 ---
if not st.session_state.logged_in:
    st.title("🔐 비디오랜딩 서비스")
    
    tab1, tab2 = st.tabs(["🔑 로그인", "📝 회원가입"])
    
    with tab1:
        st.markdown("등록된 이메일과 비밀번호로 로그인하세요.")
        with st.form("login_form"):
            login_email = st.text_input("이메일 주소", value=st.session_state.saved_email, key="login_email_input")
            login_pw = st.text_input("비밀번호", type="password", key="login_pw_input")
            remember_email = st.checkbox("이메일 주소 기억하기", value=bool(st.session_state.saved_email))
            
            login_btn = st.form_submit_button("로그인", type="primary")
            
            if login_btn:
                if login_email in st.session_state.users_db and st.session_state.users_db[login_email] == login_pw:
                    st.session_state.logged_in = True
                    st.session_state.user_email = login_email
                    
                    # URL 쿼리 파라미터에 계정 정보를 남겨 새로고침해도 유지되도록 설정
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
        with st.form("signup_form"):
            signup_email = st.text_input("사용할 이메일 주소", key="signup_email_input")
            signup_pw = st.text_input("사용할 비밀번호", type="password", key="signup_pw_input")
            signup_btn = st.form_submit_button("회원가입 완료", type="primary")
            
            if signup_btn:
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
        # 로그아웃 시 쿼리 파라미터 제거
        if "logged_in_user" in st.query_params:
            del st.query_params["logged_in_user"]
        st.rerun()

    st.sidebar.divider()
    st.sidebar.header("⚙️ 설정")
    api_key_input = st.sidebar.text_input("Gemini API Key 입력", type="password", value=os.environ.get("GEMINI_API_KEY", ""))

    st.title("🎬 비디오랜딩 (VideoLanding)")
    st.markdown(f"환영합니다, **{user_name}**님! 영상 클립을 업로드하고 미리보기와 AI 분석을 이용해 보세요.")

    # 파일 업로드 컴포넌트
    uploaded_files = st.file_uploader(
        "정리할 영상 파일을 여러 개 선택하세요 (mp4, mov, avi)", 
        type=["mp4", "mov", "avi"], 
        accept_multiple_files=True
    )

    # --- 🎥 업로드된 영상 미리보기 및 재생 섹션 ---
    if uploaded_files:
        st.divider()
        st.subheader("📺 업로드된 영상 미리보기 및 확인")
        st.markdown("선택하신 영상 중 확인하고 싶은 클립을 선택하여 바로 재생해 볼 수 있습니다.")

        file_dict = {file.name: file for file in uploaded_files}
        selected_file_name = st.selectbox("재생할 영상을 선택하세요:", list(file_dict.keys()))

        if selected_file_name:
            chosen_file = file_dict[selected_file_name]
            st.video(chosen_file)

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
                blur_score = cv2.var(gray)
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
            client = genai.Client(api_key=api_key)
            
            contents = [
                "당신은 전문 영상 편집 디렉터입니다. 사용자가 업로드한 여러 개의 영상 클립 대표 이미지들을 분석하여, 각 영상의 내용을 한 줄로 요약하고 전체 영상이 가장 자연스럽게 이어지도록 최적의 편집 순서를 매겨주세요."
            ]

            for idx, vid in enumerate(valid_videos):
                contents.append(f"\n[영상 {idx+1}: {vid['file_name']} (길이: {vid['duration']:.1f}초)]")
                for frame in vid['frames']:
                    success, buffer = cv2.imencode(".jpg", frame)
                    if success:
                        contents.append(
                            types.Part.from_bytes(
                                data=buffer.tobytes(),
                                mime_type="image/jpeg",
                            )
                        )

            contents.append("\n위 영상들을 분석해서 1) 각 영상의 내용 요약과 2) 가장 추천하는 편집 순서(번호와 요약 이유)를 보기 쉽게 정리해 줘.")

            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=contents
            )
            return response.text
        except Exception as e:
            return f"❌ Gemini AI 분석 중 오류가 발생했습니다: {e}"

    # --- 분석 및 정렬 실행 버튼 (프로그레스 바 포함) ---
    if uploaded_files:
        st.divider()
        if st.button("🚀 비디오랜딩 분석 및 정렬 시작", type="primary"):
            if not api_key_input:
                st.error("⚠️ 좌측 사이드바에 Gemini API Key를 먼저 입력해주세요!")
            else:
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                status_text.text("🔄 영상을 분석할 준비를 하고 있습니다...")
                progress_bar.progress(10)
                
                valid_clips = []
                total_files = len(uploaded_files)
                
                st.subheader("📊 1단계: 개별 영상 품질 및 블러 분석 결과")
                
                for idx, uploaded_file in enumerate(uploaded_files):
                    current_progress = 10 + int((idx / total_files) * 50)
                    progress_bar.progress(current_progress)
                    status_text.text(f"🔍 분석 중 ({idx+1}/{total_files}): {uploaded_file.name}")
                    
                    tfile = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[1])
                    tfile.write(uploaded_file.read())
                    tfile.close()

                    result = analyze_and_filter_video(tfile.name, blur_threshold=80.0)
                    
                    with st.container(border=True):
                        st.markdown(f"**파일명: {result['file_name']}**")
                        st.text(f"영상 길이: {result['duration']:.1f}초 | 선명도 점수: {result['avg_blur_score']:.1f}")
                        
                        if result.get("is_blurry"):
                            st.error("🚨 불량 판정 (흔들림/흐림 심함 - 제외 후보)")
                        else:
                            st.success("✅ 통과 (편집 후보)")
                            valid_clips.append(result)
                    
                    os.unlink(tfile.name)
                
                if valid_clips:
                    progress_bar.progress(70)
                    status_text.text("🤖 Gemini AI 디렉터가 최적의 스토리라인을 구성하는 중입니다...")
                    
                    st.divider()
                    st.subheader("🤖 2단계: Gemini 디렉터의 편집 순서 및 내용 가이드")
                    ai_result = ai_organize_videos_with_gemini(valid_clips, api_key_input)
                    
                    progress_bar.progress(100)
                    status_text.text("✨ 분석이 완료되었습니다!")
                    time.sleep(0.5)
                    status_text.empty()
                    progress_bar.empty()
                    
                    st.markdown(ai_result)
                else:
                    progress_bar.progress(100)
                    status_text.empty()
                    st.warning("⚠️ 통과된 유효한 영상이 없습니다. 블러 기준을 조절해 보세요.")
    else:
        st.info("💡 위 업로드 버튼을 눌러 편집할 영상들을 선택해 주세요.")
