# app/utils/mood_detector.py
# Note: This is an advanced, optional feature. Requires `pip install deepface opencv-python`.

import cv2
from deepface import DeepFace

def detect_emotion_from_webcam(duration_seconds=5):
    """
    Captures video from webcam for a few seconds, detects the dominant emotion.
    Returns the dominant emotion as a string (e.g., 'happy', 'sad', 'neutral').
    """
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Cannot open webcam.")
        return "neutral" # Default fallback

    start_time = cv2.getTickCount()
    emotion_counts = {}
    
    print(f"Analyzing mood for {duration_seconds} seconds... Please look at the camera.")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Analyze frame for emotion
        try:
            # enforce_detection=False prevents it from throwing an error if no face is found
            result = DeepFace.analyze(frame, actions=['emotion'], enforce_detection=False)
            
            # DeepFace returns a list of dicts, one for each face
            if isinstance(result, list) and result:
                dominant_emotion = result['dominant_emotion']
                emotion_counts[dominant_emotion] = emotion_counts.get(dominant_emotion, 0) + 1
        except Exception as e:
            # Ignore frames where analysis fails
            pass
        
        # Display the frame (optional, good for user feedback)
        cv2.imshow('Mood Detection', frame)

        # Check if duration has passed or user quits
        elapsed_time = (cv2.getTickCount() - start_time) / cv2.getTickFrequency()
        if elapsed_time > duration_seconds or cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

    if not emotion_counts:
        return "neutral" # Default if no emotions were detected

    # Return the most frequently detected emotion
    dominant_mood = max(emotion_counts, key=emotion_counts.get)
    
    # Map detected emotions to the moods our recommender understands
    mood_map = {
        'happy': 'happy',
        'sad': 'stressed', # Assuming sad might want calming content
        'angry': 'stressed',
        'neutral': 'curious',
        'surprise': 'curious',
        'fear': 'stressed',
        'disgust': 'stressed' # A reasonable default
    }
    
    return mood_map.get(dominant_mood, "inspired")

if __name__ == '__main__':
    user_mood = detect_emotion_from_webcam()
    print(f"Detected dominant mood: {user_mood}")