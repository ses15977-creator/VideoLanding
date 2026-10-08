import os
import cv2
import numpy as np
import base64
from openai import OpenAI

# OpenAI 클라이언트 초기화 (환경 변수 또는 직접 API 키 입력)
# API 키는 환경변수(OPENAI_API_KEY)로 설정하는 것이 안전합니다.
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

def analyze_and_filter_video(video_path, blur_threshold=100.0, frame_interval=30):
    """
    1단계: 영상 파일 분석 및 흔들림(블러) 필터링, 핵심 프레임 추출
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return {"error": f"영상을 열 수 없습니다: {video_path}"}

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps if fps > 0 else 0

    frame_count = 0
    blur_scores = []
    extracted_frames = [] # AI에게 보낼 대표 프레임 이미지들 저장
    
    print(f"\n[분석 중] {os.path.basename(video_path)} (길이: {duration:.1f}초)")

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        # 지정된 간격마다 프레임 분석 및 추출
        if frame_count % frame_interval == 0:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            blur_score = cv2.var(gray)
            blur_scores.append(blur_score)

            # AI 분석용으로 적절한 크기로 리사이즈하여 보관
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
        "frames": extracted_frames[:3] # AI에게는 대표 프레임 최대 3장만 전달 (비용 및 속도 최적화)
    }

def encode_image_to_base64(cv2_image):
    """OpenCV 이미지를 base64 문자열로 변환 (AI 전송용)"""
    success, buffer = cv2.imencode(".jpg", cv2_image)
    if not success:
        return None
    return base64.b64encode(buffer).decode("utf-8")

def ai_organize_videos(valid_videos):
    """
    2단계: 살아남은 영상들의 대표 프레임을 AI에게 보내어 
    내용 분석 및 최적의 편집 순서 정렬 수행
    """
    if not valid_videos:
        print("🚨 분석할 유효한 영상이 없습니다.")
        return

    print("\n🤖 [AI 비전 분석 중] 영상들의 내용을 파악하고 최적의 편집 순서를 정리하고 있습니다...")

    # AI에게 보낼 메시지 구성
    messages = [
        {
            "role": "system",
            "content": "당신은 전문 영상 편집 디렉터입니다. 사용자가 업로드한 여러 개의 영상 클립 대표 이미지들을 분석하여, 각 영상의 내용을 한 줄로 요약하고 전체 영상이 가장 자연스럽게 이어지도록(기승전결 또는 촬영 동선에 맞춰) 최적의 편집 순서를 매겨주세요."
        }
    ]

    user_content = []
    for idx, vid in enumerate(valid_videos):
        user_content.append(f"영상 {idx+1}: {vid['file_name']} (길이: {vid['duration']:.1f}초)")
        # 각 영상의 대표 프레임들을 이미지로 첨부
        for f_idx, frame in enumerate(vid['frames']):
            base64_img = encode_image_to_base64(frame)
            if base64_img:
                user_content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}
                })

    user_content.append("위 영상들을 분석해서 1) 각 영상의 내용 요약과 2) 가장 추천하는 편집 순서(번호와 이유)를 보기 쉽게 정리해 줘.")
    messages.append({"role": "user", "content": user_content})

    try:
        # GPT-4o 모델을 이용한 멀티모달 분석
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            max_tokens=1000
        )
        print("\n✨ --- [비디오랜딩 AI 분석 및 편집 가이드] ---")
        print(response.choices[0].message.content)
    except Exception as e:
        print(f"❌ AI 분석 중 오류가 발생했습니다 (API 키를 확인해주세요): {e}")

# --- [테스트 실행] ---
if __name__ == "__main__":
    # 예시: 현재 폴더에 있는 영상 파일들 목록
    sample_videos = ["test_clip1.mp4", "test_clip2.mp4"] 
    
    valid_clips = []
    
    for path in sample_videos:
        if os.path.exists(path):
            result = analyze_and_filter_video(path, blur_threshold=80.0)
            print(f"- 블러 점수: {result['avg_blur_score']:.1f}")
            
            if result.get("is_blurry"):
                print(f"🚨 [제외] {result['file_name']} -> 흔들림이 심해 제외되었습니다.")
            else:
                print(f"✅ [통과] {result['file_name']} -> 편집 후보로 등록되었습니다.")
                valid_clips.append(result)
        else:
            print(f"'{path}' 파일을 찾을 수 없어 건너뜁니다.")

    # 통과된 영상들이 있다면 AI 분석 실행
    if valid_clips:
        ai_organize_videos(valid_clips)
