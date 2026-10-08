import os
import cv2
import numpy as np

def analyze_and_filter_video(video_path, blur_threshold=100.0, frame_interval=30):
    """
    영상 파일 하나를 분석하여 
    1) 흔들림(블러) 점수 계산 및 불량 판정
    2) 핵심 프레임(이미지) 추출
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return {"error": f"영상을 열 수 없습니다: {video_path}"}

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps if fps > 0 else 0

    frame_count = 0
    blur_scores = []
    extracted_frames = []
    
    print(f"\n[분석 중] {os.path.basename(video_path)} (길이: {duration:.1f}초)")

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        # 지정된 간격(예: 30프레임마다 = 약 1초마다)으로 프레임 추출 및 분석
        if frame_count % frame_interval == 0:
            # 흑백으로 변환 후 라플라시안 분산(선명도/흔들림 측정) 계산
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            blur_score = cv2.var(gray) # 라플라시안 분산 값
            blur_scores.append(blur_score)

            # 테스트용으로 대표 프레임 이미지 메모리에 저장 (나중에 AI에게 보낼 용도)
            extracted_frames.append((frame_count, frame))

        frame_count += 1

    cap.release()

    # 평균 블러 점수 계산 (점수가 낮을수록 흔들리고 흐릿한 영상)
    avg_blur_score = np.mean(blur_scores) if blur_scores else 0
    
    # 판정 기준: 평균 블러 점수가 설정값보다 낮으면 '불량(흔들림 심함)'으로 판단
    is_blurry = avg_blur_score < blur_threshold

    return {
        "file_name": os.path.basename(video_path),
        "duration": duration,
        "avg_blur_score": avg_blur_score,
        "is_blurry": is_blurry,
        "extracted_frames_count": len(extracted_frames)
    }

# --- [테스트 실행 예시] ---
if __name__ == "__main__":
    # 테스트할 영상 폴더 경로 지정 (예시)
    sample_video = "test_clip.mp4" 
    
    if os.path.exists(sample_video):
        result = analyze_and_filter_video(sample_video, blur_threshold=80.0, frame_interval=30)
        print("\n--- [분석 결과 리포트] ---")
        for key, value in result.items():
            print(f"- {key}: {value}")
        
        if result.get("is_blurry"):
            print("🚨 [결과] 이 영상은 흔들림이나 흐림이 심하여 '제외 후보'로 분류되었습니다.")
        else:
            print("✅ [결과] 화질과 선명도가 양호하여 편집 후보로 통과되었습니다!")
    else:
        print(f"'{sample_video}' 파일이 없습니다. 테스트할 영상 파일 경로를 확인해 주세요.")
