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

pygame.init()

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Dianas")

clock = pygame.time.Clock()

BACKGROUND_IMAGE = "fondo.png"

background = pygame.image.load(BACKGROUND_IMAGE).convert()
background = pygame.transform.scale(
    background,
    (WIDTH, HEIGHT)
)

font = pygame.font.Font(None, 36)


# =========================================================
# VARIABLES COMPARTIDAS ENTRE HILOS
# =========================================================

running = True

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
    return {
        "x": random.randint(
            TARGET_RADIUS,
            WIDTH - TARGET_RADIUS
        ),
        "y": random.randint(
            TARGET_RADIUS + 60,
            HEIGHT - TARGET_RADIUS
        )
    }


for _ in range(8):
    targets.append(crear_diana())


def dibujar_diana(x, y):

    # Anillo exterior
    pygame.draw.circle(
        screen,
        (220, 220, 220),
        (x, y),
        TARGET_RADIUS
    )

    # Anillo rojo
    pygame.draw.circle(
        screen,
        (200, 40, 40),
        (x, y),
        int(TARGET_RADIUS * 0.75)
    )

    # Anillo blanco
    pygame.draw.circle(
        screen,
        (245, 245, 245),
        (x, y),
        int(TARGET_RADIUS * 0.50)
    )

    # Centro
    pygame.draw.circle(
        screen,
        (220, 40, 40),
        (x, y),
        int(TARGET_RADIUS * 0.25)
    )


# =========================================================
# PUNTUACIÓN
# =========================================================

def calcular_puntuacion(x, y, diana):

    distancia = math.hypot(
        x - diana["x"],
        y - diana["y"]
    )

    if distancia > TARGET_RADIUS:
        return 0

    puntuacion = int(
        100 * (1 - distancia / TARGET_RADIUS)
    )

    return max(10, puntuacion)


# =========================================================
# HILO DE MEDIAPIPE + OPENCV
# =========================================================

def camara_thread():

    global running
    global hand_x
    global hand_y

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
            frame_rgb = cv2.cvtColor(
                frame,
                cv2.COLOR_BGR2RGB
            )

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

                height, width, _ = frame.shape

                # Coordenadas de cámara
                camera_x = int(
                    index_finger.x * width
                )

                camera_y = int(
                    index_finger.y * height
                )

                # Convertir a coordenadas de Pygame
                pygame_x = int(
                    index_finger.x * WIDTH
                )

                pygame_y = int(
                    index_finger.y * HEIGHT
                )

                # Guardar coordenadas de forma segura
                with lock:
                    hand_x = pygame_x
                    hand_y = pygame_y

                # Dibujar mano
                for hand_landmarks in results.multi_hand_landmarks:

                    mp_drawing.draw_landmarks(
                        frame,
                        hand_landmarks,
                        mp_hands.HAND_CONNECTIONS
                    )

            # Mostrar cámara
            cv2.imshow(
                "Camara - MediaPipe",
                frame
            )

            # ESC para salir
            if cv2.waitKey(1) & 0xFF == 27:
                running = False
                break

    cap.release()
    cv2.destroyAllWindows()


# =========================================================
# CREAR HILO DE CÁMARA
# =========================================================

thread_camera = threading.Thread(
    target=camara_thread
)

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

                    distancia = math.hypot(
                        mouse_x - diana["x"],
                        mouse_y - diana["y"]
                    )

                    if distancia <= TARGET_RADIUS:

                        puntos = calcular_puntuacion(
                            mouse_x,
                            mouse_y,
                            diana
                        )

                        puntuacion_total += puntos

                        targets.remove(diana)

                        break


    # =====================================================
    # OBTENER POSICIÓN DE LA MANO
    # =====================================================

    with lock:
        current_hand_x = hand_x
        current_hand_y = hand_y


    # =====================================================
    # COMPROBAR SI LA MANO TOCA UNA DIANA
    # =====================================================

    for diana in targets[:]:

        distancia = math.hypot(
            current_hand_x - diana["x"],
            current_hand_y - diana["y"]
        )

        if distancia <= TARGET_RADIUS:

            puntos = calcular_puntuacion(
                current_hand_x,
                current_hand_y,
                diana
            )

            puntuacion_total += puntos

            targets.remove(diana)

            break


    # =====================================================
    # FONDO
    # =====================================================

    screen.blit(
        background,
        (0, 0)
    )


    # =====================================================
    # DIANAS
    # =====================================================

    for diana in targets:

        dibujar_diana(
            diana["x"],
            diana["y"]
        )


    # =====================================================
    # PUNTUACIÓN
    # =====================================================

    texto = font.render(
        f"Puntuación: {puntuacion_total}",
        True,
        (255, 255, 255)
    )

    screen.blit(
        texto,
        (20, 20)
    )


    # =====================================================
    # COORDENADAS DE LA MANO
    # =====================================================

    coordenadas = font.render(
        f"Apuntando: ({current_hand_x}, {current_hand_y})",
        True,
        (255, 255, 255)
    )

    screen.blit(
        coordenadas,
        (20, 55)
    )


    # =====================================================
    # DIBUJAR PUNTERO DE LA MANO
    # =====================================================

    if current_hand_x != 0 and current_hand_y != 0:

        pygame.draw.circle(
            screen,
            (0, 255, 0),
            (current_hand_x, current_hand_y),
            10
        )

        pygame.draw.circle(
            screen,
            (255, 255, 255),
            (current_hand_x, current_hand_y),
            15,
            2
        )


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