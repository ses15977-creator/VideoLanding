import os
import cv2
import numpy as np
import base64
import tempfile
import streamlit as st
from openai import OpenAI

# Streamlit 페이지 설정
st.set_page_config(page_title="비디오랜딩 (VideoLanding)", page_icon="🎬", layout="wide")

st.title("🎬 비디오랜딩 (VideoLanding)")
st.markdown("편집 전 영상 클립들을 업로드하면, **흔들린 불량 영상 자동 필터링**부터 **AI 비전 분석을 통한 최적의 편집 순서 정렬**까지 한 번에 처리해 줍니다!")

# 사이드바 설정 (API 키 입력)
st.sidebar.header("⚙️ 설정")
api_key_input = st.sidebar.text_input("OpenAI API Key 입력", type="password", value=os.environ.get("OPENAI_API_KEY", ""))

# 파일 업로드 컴포넌트
uploaded_files = st.file_uploader("정리할 영상 파일을 여러 개 업로드하세요 (mp4, mov, avi 등)", type=["mp4", "mov", "avi"], accept_multiple_files=True)

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

            small_frame = cv2.resize(frame, (512, 512))
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

def encode_image_to_base64(cv2_image):
    success, buffer = cv2.imencode(".jpg", cv2_image)
    if not success:
        return None
    return base64.b64encode(buffer).decode("utf-8")

def ai_organize_videos(valid_videos, api_key):
    client = OpenAI(api_key=api_key)
    
    messages = [
        {
            "role": "system",
            "content": "당신은 전문 영상 편집 디렉터입니다. 사용자가 업로드한 여러 개의 영상 클립 대표 이미지들을 분석하여, 각 영상의 내용을 한 줄로 요약하고 전체 영상이 가장 자연스럽게 이어지도록 최적의 편집 순서를 매겨주세요."
        }
    ]

    user_content = []
    for idx, vid in enumerate(valid_videos):
        user_content.append(f"영상 {idx+1}: {vid['file_name']} (길이: {vid['duration']:.1f}초)")
        for frame in vid['frames']:
            base64_img = encode_image_to_base64(frame)
            if base64_img:
                user_content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}
                })

    user_content.append("위 영상들을 분석해서 1) 각 영상의 내용 요약과 2) 가장 추천하는 편집 순서(번호와 이유)를 보기 쉽게 정리해 줘.")
    messages.append({"role": "user", "content": user_content})

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            max_tokens=1000
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"❌ AI 분석 중 오류가 발생했습니다: {e}"

# --- 실행 버튼 ---
if uploaded_files:
    if st.button("🚀 비디오랜딩 분석 및 정렬 시작", type="primary"):
        if not api_key_input:
            st.error("⚠️ 사이드바에 OpenAI API Key를 먼저 입력해주세요!")
        else:
            with st.spinner("영상을 분석하고 AI가 스토리라인을 짜는 중입니다... 잠시만 기다려주세요!"):
                valid_clips = []
                
                st.subheader("📊 1단계: 개별 영상 품질 및 블러 분석 결과")
                
                cols = st.columns(len(uploaded_files))
                
                for idx, uploaded_file in enumerate(uploaded_files):
                    # 임시 파일로 저장하여 OpenCV로 읽기
                    tfile = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[1])
                    tfile.write(uploaded_file.read())
                    tfile.close()

                    result = analyze_and_filter_video(tfile.name, blur_threshold=80.0)
                    
                    with st.container():
                        st.markdown(f"**파일명: {result['file_name']}**")
                        st.text(f"영상 길이: {result['duration']:.1f}초")
                        st.text(f"선명도(블러) 점수: {result['avg_blur_score']:.1f}")
                        
                        if result.get("is_blurry"):
                            st.error("🚨 불량 판정 (흔들림/흐림 심함 - 제외 후보)")
                        else:
                            st.success("✅ 통과 (편집 후보)")
                            valid_clips.append(result)
                    
                    # 사용된 임시 파일 삭제
                    os.unlink(tfile.name)
                
                # 2단계: AI 분석 실행
                if valid_clips:
                    st.divider()
                    st.subheader("🤖 2단계: AI 디렉터의 편집 순서 및 내용 가이드")
                    ai_result = ai_organize_videos(valid_clips, api_key_input)
                    st.markdown(ai_result)
                else:
                    st.warning("⚠️ 통과된 유효한 영상이 없어 AI 분석을 진행할 수 없습니다. (블러 기준을 낮춰보세요)")
else:
    st.info("💡 위 업로드 창에 편집할 영상 파일들을 드래그해서 올려주세요.")
