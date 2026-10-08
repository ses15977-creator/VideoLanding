import os
import cv2
import numpy as np
import tempfile
import streamlit as st
from google import genai
from google.genai import types
from streamlit_google_auth import Authenticate

# Streamlit 페이지 설정 (모바일 최적화)
st.set_page_config(
    page_title="비디오랜딩 (VideoLanding)", 
    page_icon="🎬", 
    layout="centered"
)

# 모바일 화면을 위한 커스텀 CSS
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

# --- 구글 인증(OAuth) 설정 ---
# ※ 참고: 구글 로그인을 완벽하게 동작시키려면 Google Cloud Console에서 
# OAuth 클라이언트 ID를 발급받아 st.secrets에 등록하거나 아래에 입력해야 합니다.
# 테스트를 위해 우선 간편 로그인 모드와 구글 연동 버튼이 함께 작동하도록 구성했습니다.

client_id = st.secrets.get("GOOGLE_CLIENT_ID", "YOUR_GOOGLE_CLIENT_ID")
client_secret = st.secrets.get("GOOGLE_CLIENT_SECRET", "YOUR_GOOGLE_CLIENT_SECRET")
redirect_uri = st.secrets.get("GOOGLE_REDIRECT_URI", "https://videolanding-gmynymie6l6wakszpc8abt.streamlit.app/")

authenticator = Authenticate(
    secret_credentials_path=None,
    client_id=client_id,
    client_secret=client_secret,
    redirect_uri=redirect_uri,
    cookie_cookie_name="video_landing_auth",
    cookie_key="video_landing_secret",
    cookie_expiry_days=30,
)

# 세션 상태 확인
authenticator.check_authorization()

# --- 로그인 상태 확인 ---
if not st.session_state.get('connected', False):
    st.title("🔐 비디오랜딩 간편 로그인")
    st.markdown("구글 계정으로 안전하게 로그인하여 나만의 영상 편집 공간을 이용하세요.")
    
    col1, col2 = st.columns(2)
    with col1:
        # 공식 구글 로그인 버튼 렌더링
        authenticator.login()
    
    with col2:
        # 만약 클라우드 키 설정 전이라도 테스트할 수 있는 간편 이메일 로그인 제공
        with st.form("quick_login_form"):
            st.markdown("---")
            st.text("또는 이메일로 바로 시작하기")
            quick_email = st.text_input("구글 이메일 주소 입력")
            quick_btn = st.form_submit_button("🚀 간편 로그인", type="primary")
            if quick_btn and quick_email and "@" in quick_email:
                st.session_state['connected'] = True
                st.session_state['user_info'] = {'email': quick_email, 'name': quick_email.split('@')[0]}
                st.rerun()

else:
    # --- 로그인 완료 후 메인 서비스 화면 ---
    user_info = st.session_state.get('user_info', {})
    user_email = user_info.get('email', '사용자')
    user_name = user_info.get('name', '크리에이터')

    st.sidebar.markdown(f"👤 **접속 계정:**\n`{user_email}`")
    
    if st.sidebar.button("로그아웃"):
        authenticator.logout()
        st.session_state['connected'] = False
        st.session_state['user_info'] = {}
        st.rerun()

    st.sidebar.divider()
    st.sidebar.header("⚙️ 설정")
    api_key_input = st.sidebar.text_input("Gemini API Key 입력", type="password", value=os.environ.get("GEMINI_API_KEY", ""))

    st.title("🎬 비디오랜딩 (VideoLanding)")
    st.markdown(f"환영합니다, **{user_name}**님! 편집 전 영상 클립들을 올려주시면 AI가 분석 및 정리를 도와드립니다.")

    # 파일 업로드 컴포넌트
    uploaded_files = st.file_uploader("정리할 영상 파일을 여러 개 선택하세요 (mp4, mov, avi)", type=["mp4", "mov", "avi"], accept_multiple_files=True)

    def analyze_and_filter_video(video_path, blur_threshold=100.0, frame_interval=30):
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return {"error": f"영상을 열 수 없습니다."}

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

            contents.append("\n위 영상들을 분석해서 1) 각 영상의 내용 요약과 2) 가장 추천하는 편집 순서(번호와 이유)를 보기 쉽게 정리해 줘.")

            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=contents
            )
            return response.text
        except Exception as e:
            return f"❌ Gemini AI 분석 중 오류가 발생했습니다: {e}"

    # --- 실행 버튼 ---
    if uploaded_files:
        if st.button("🚀 비디오랜딩 분석 및 정렬 시작", type="primary"):
            if not api_key_input:
                st.error("⚠️ 좌측 사이드바에 Gemini API Key를 먼저 입력해주세요!")
            else:
                with st.spinner(f"{user_name}님의 영상을 분석하고 Gemini AI가 스토리라인을 짜는 중입니다..."):
                    valid_clips = []
                    
                    st.subheader("📊 1단계: 개별 영상 품질 및 블러 분석 결과")
                    
                    for uploaded_file in uploaded_files:
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
                    
                    # 2단계: Gemini AI 분석 실행
                    if valid_clips:
                        st.divider()
                        st.subheader("🤖 2단계: Gemini 디렉터의 편집 순서 및 내용 가이드")
                        ai_result = ai_organize_videos_with_gemini(valid_clips, api_key_input)
                        st.markdown(ai_result)
                    else:
                        st.warning("⚠️ 통과된 유효한 영상이 없습니다. 블러 기준을 조절해 보세요.")
    else:
        st.info("💡 위 업로드 버튼을 눌러 편집할 영상들을 선택해 주세요.")
