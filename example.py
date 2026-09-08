import cv2
import mediapipe as mp
mp_drawing = mp.solutions.drawing_utils
mp_hands = mp.solutions.hands
with mp_hands.Hands(
static_image_mode=True,
max_num_hands=2,
min_detection_confidence=0.5) as hands:
    #image = cv2.imread("C:/path absoluto/ConManos.jpg")
    image = cv2.imread("./Imagenes/ConManos.jpg")
    height, width, _ = image.shape
    image = cv2.flip(image, 1)
    image_rgb =cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    results = hands.process(image_rgb)
    print('Handedness:', results.multi_handedness)
    if results.multi_hand_landmarks is not None:
        # Dibujando los puntos y las conexiones mediante mp_drawing
        for hand_landmarks in results.multi_hand_landmarks:
            mp_drawing.draw_landmarks(
            image, hand_landmarks, mp_hands.HAND_CONNECTIONS,
            mp_drawing.DrawingSpec(color=(50,50,255), thickness=4, circle_radius=5),
            mp_drawing.DrawingSpec(color=(255,0,0), thickness=4))
    image = cv2.flip(image, 1)
cv2.imshow("Imagen",image)
cv2.waitKey(0)
cv2.destroyAllWindows()
