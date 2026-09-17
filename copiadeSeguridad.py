import pygame
import random
import math
import mediapipe as mp
import cv2
import threading

# =========================================================
# CONFIGURACIÓN
# =========================================================

WIDTH = 1000
HEIGHT = 700

DPULGARARRIBA = 0.5
DMANOABIERTA = 0.5

pygame.init()

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Dianas")

clock = pygame.time.Clock()

BACKGROUND_IMAGE = "fondo.png"

background = pygame.image.load(BACKGROUND_IMAGE).convert()
background = pygame.transform.scale(background,(WIDTH, HEIGHT))

font = pygame.font.Font(None, 36)


# =========================================================
# VARIABLES COMPARTIDAS ENTRE HILOS
# =========================================================

running = True

trigger_gesture = False

stop_gesture = False



# Coordenadas de la mano
hand_x = 0
hand_y = 0

# Lock para evitar problemas al acceder a las variables
lock = threading.Lock()


# =========================================================
# DIANAS
# =========================================================

TARGET_RADIUS = 40

targets = []


def crear_diana():
    return { #creamos la diana con sus datos y devolvemos un diccionario
        "x": random.randint(TARGET_RADIUS,WIDTH - TARGET_RADIUS),"y": random.randint(TARGET_RADIUS + 60,HEIGHT - TARGET_RADIUS)
    }


for _ in range(8):
    targets.append(crear_diana())


def dibujar_diana(x, y):

    # Anillo exterior
    pygame.draw.circle(screen, (220, 220, 220), (x, y),TARGET_RADIUS)

    # Anillo rojo
    pygame.draw.circle(screen, (200, 40, 40), (x, y), int(TARGET_RADIUS * 0.75))

    # Anillo blanco
    pygame.draw.circle(screen, (245, 245, 245), (x, y), int(TARGET_RADIUS * 0.50))

    # Centro
    pygame.draw.circle( screen, (220, 40, 40), (x, y), int(TARGET_RADIUS * 0.25))


# =========================================================
# PUNTUACIÓN
# =========================================================

def calcular_puntuacion(x, y, diana):

    distancia = math.hypot(x - diana["x"],y - diana["y"])

    if distancia > TARGET_RADIUS:
        return 0

    puntuacion = int(100 * (1 - distancia / TARGET_RADIUS))

    return max(10, puntuacion)

# Calcular posición relativa
def calcularDistancia(p1x, p1y, p2x, p2y):
    return math.hypot(p1x - p2x, p1y - p2y)

# Detectar pulgar abajo
def pulgar_abierto(hand_landmarks) -> bool:

    thumb_up = False

    lm = hand_landmarks.landmark

    # Punta del pulgar
    thumb_tip = lm[4]

    # Punta del índice
    index_tip = lm[8]

    # Referencia para normalizar el tamaño de la mano
    wrist = lm[0]
    middle_mcp = lm[9]

    # calculamos la posicion del pulgar
    d_thumb_index = calcularDistancia(thumb_tip.x,thumb_tip.y,index_tip.x, index_tip.y)

    # Tamaño de la mano
    hand_size = calcularDistancia(wrist.x,wrist.y,middle_mcp.x,middle_mcp.y)

    # Distancia relativa
    d_relativa = d_thumb_index / hand_size

    if d_relativa < DPULGARARRIBA :
        thumb_up = True

    return thumb_up

# Detectar stop
def palma_abierta(hand_landmarks) -> bool:

    open_palm = False

    lm = hand_landmarks.landmark

    # Punta del pulgar
    thumb_tip = lm[4]

    # Punta del índice
    index_tip = lm[8]

    # Punta del meñique
    pinky_tip = lm[20]

    # Referencia para normalizar el tamaño de la mano
    wrist = lm[0]
    middle_mcp = lm[9]

    # calculamos la posicion del pulgar
    d_thumb_wrist = calcularDistancia(thumb_tip.x,thumb_tip.y,wrist.x, wrist.y)
    d_pinky_wrist = calcularDistancia(pinky_tip.x,pinky_tip.y, wrist.x, wrist.y)
    d_index_wrist = calcularDistancia(index_tip.x,index_tip.y, wrist.x, wrist.y)

    # Tamaño de la mano
    hand_size = calcularDistancia(wrist.x,wrist.y,middle_mcp.x,middle_mcp.y)

    # Distancia relativa
    d_thumb_wrist = d_thumb_wrist / hand_size
    d_pinky_wrist = d_pinky_wrist / hand_size
    d_index_wrist = d_index_wrist / hand_size

    print(d_thumb_wrist)
    print(d_pinky_wrist)
    print(d_index_wrist)

    if d_thumb_wrist > DMANOABIERTA and d_pinky_wrist > DMANOABIERTA and d_index_wrist > DMANOABIERTA :
        open_palm = True

    return open_palm
               

   


# =========================================================
# HILO DE MEDIAPIPE + OPENCV
# =========================================================

def camara_thread():

    global running
    global hand_x
    global hand_y
    global trigger_gesture
    global stop_gesture

    mp_drawing = mp.solutions.drawing_utils
    mp_hands = mp.solutions.hands

    cap = cv2.VideoCapture(0)

    with mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=2,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5
    ) as hands:

        while running:

            ret, frame = cap.read()

            if not ret:
                print("No se pudo leer la cámara")
                break

            # Espejo
            frame = cv2.flip(frame, 1)

            # RGB para MediaPipe
            frame_rgb = cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)

            # Detectar manos
            results = hands.process(frame_rgb)

            # -------------------------------------------------
            # OBTENER COORDENADAS DE LA MANO
            # -------------------------------------------------

            if results.multi_hand_landmarks:

                # Usamos la primera mano detectada
                hand = results.multi_hand_landmarks[0]

                # Landmark 8 = punta del dedo índice
                index_finger = hand.landmark[8]
                thumb_finger = hand.landmark[4]



                #print("dedo indíce")

                #trigger_gesture = pulgar_abierto(hand)

                
                #stop_gesture = palma_abierta(hand)

                if palma_abierta(hand): #Comprobamos si hay stop
                    stop_gesture_local = True
                    trigger_gesture_local = False
                elif pulgar_abierto(hand): #Comprobamos si hay disparo
                    trigger_gesture_local = True
                    stop_gesture_local = False
                else: #limpiamos posibles gestos anteriores sin resolver
                    trigger_gesture_local = False
                    stop_gesture_local = False

                height, width, _ = frame.shape

                # Coordenadas de  ----METER EN UNA FUNCION----
                camera_x = int(index_finger.x * width)

                camera_y = int(index_finger.y * height)

                # Convertir a coordenadas de Pygame
                pygame_x = int(index_finger.x * WIDTH)

                pygame_y = int(index_finger.y * HEIGHT)

                # Guardar coordenadas de forma segura
                with lock:
                    hand_x = pygame_x
                    hand_y = pygame_y
                    trigger_gesture = pulgar_abierto(hand)
                    


                # Dibujar mano
                for hand_landmarks in results.multi_hand_landmarks:

                    mp_drawing.draw_landmarks(frame,hand_landmarks,mp_hands.HAND_CONNECTIONS)

            # Mostrar cámara
            cv2.imshow("Camara - MediaPipe",frame)

            # ESC para salir
            if cv2.waitKey(1) & 0xFF == 27:
                running = False
                break

    cap.release()
    cv2.destroyAllWindows()


# =========================================================
# CREAR HILO DE CÁMARA
# =========================================================

thread_camera = threading.Thread(target=camara_thread)

thread_camera.daemon = True
thread_camera.start()


# =========================================================
# BUCLE PRINCIPAL DE PYGAME
# =========================================================

puntuacion_total = 0

while running:

    # =====================================================
    # EVENTOS
    # =====================================================

    for event in pygame.event.get():

        if event.type == pygame.QUIT:
            running = False

        # También puedes disparar con el ratón
        elif event.type == pygame.MOUSEBUTTONDOWN:

            if event.button == 1:

                mouse_x, mouse_y = pygame.mouse.get_pos()

                for diana in targets[:]:

                    distancia = math.hypot(mouse_x - diana["x"],mouse_y - diana["y"])
    
                    if distancia <= TARGET_RADIUS :

                        puntos = calcular_puntuacion(mouse_x,mouse_y,diana)

                        puntuacion_total += puntos

                        targets.remove(diana)

                        break


    # =====================================================
    # OBTENER POSICIÓN DE LA MANO
    # =====================================================

    with lock:
        current_hand_x = hand_x
        current_hand_y = hand_y
        current_trigger = trigger_gesture
        current_stop = stop_gesture


    # =====================================================
    # COMPROBAR SI LA MANO TOCA UNA DIANA
    # =====================================================

    for diana in targets[:]:

        if trigger_gesture :
            print("Disparo")
        if stop_gesture :
            print("Stop")
        distancia = math.hypot(current_hand_x - diana["x"],current_hand_y - diana["y"])

        if distancia <= TARGET_RADIUS and trigger_gesture: #si las posiciones coinciden y ejecutar el trigger

            puntos = calcular_puntuacion(current_hand_x,current_hand_y,diana)

            puntuacion_total += puntos

            targets.remove(diana)

            break


    # =====================================================
    # FONDO
    # =====================================================

    screen.blit(background,(0, 0))


    # =====================================================
    # DIANAS
    # =====================================================

    for diana in targets:

        dibujar_diana(diana["x"],diana["y"])


    # =====================================================
    # PUNTUACIÓN
    # =====================================================

    texto = font.render(f"Puntuación: {puntuacion_total}",True,(255, 255, 255))

    screen.blit(texto,(20, 20))


    # =====================================================
    # COORDENADAS DE LA MANO
    # =====================================================

    coordenadas = font.render(f"Apuntando: ({current_hand_x}, {current_hand_y})",True,(255, 255, 255))

    screen.blit(coordenadas,(20, 55))


    # =====================================================
    # DIBUJAR PUNTERO DE LA MANO
    # =====================================================

    if current_hand_x != 0 and current_hand_y != 0:

        pygame.draw.circle(screen,(0, 255, 0), (current_hand_x, current_hand_y),10)

        pygame.draw.circle(screen,(255, 255, 255),(current_hand_x, current_hand_y),15,2)

    # =====================================================
    # ACTUALIZAR PANTALLA
    # =====================================================

    pygame.display.flip()

    clock.tick(60)


# =========================================================
# FINALIZAR
# =========================================================

running = False

thread_camera.join(timeout=1)

pygame.quit()
cv2.destroyAllWindows()