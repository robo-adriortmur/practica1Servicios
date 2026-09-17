import pygame
import random
import math
import mediapipe as mp
import cv2
import threading
import sys
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

# ==========================================
# 1. CLASE BARRA DE VIDA
# ==========================================
class BarraVida:
    def __init__(self, x, y, ancho, alto, vida_maxima):
        self.x = x
        self.y = y
        self.ancho = ancho
        self.alto = alto
        self.vida_maxima = vida_maxima
        self.vida_actual = vida_maxima
        self.vida_animada = vida_maxima  # Controla la barra visual que baja suavemente

    def recibir_dano(self, cantidad):
        self.vida_actual = max(self.vida_actual - cantidad, 0)

    def curar(self, cantidad):
        self.vida_actual = min(self.vida_actual + cantidad, self.vida_maxima)

    def dibujar(self, superficie):
        # 1. Efecto de interpolación: acerca la barra animada a la real suavemente
        self.vida_animada += (self.vida_actual - self.vida_animada) * 0.1

        # 2. Calcular los anchos proporcionales
        ancho_actual = (self.vida_actual / self.vida_maxima) * self.ancho
        ancho_animado = (self.vida_animada / self.vida_maxima) * self.ancho

        # 3. Definir los rectángulos
        rect_fondo = pygame.Rect(self.x, self.y, self.ancho, self.alto)
        rect_animado = pygame.Rect(self.x, self.y, ancho_animado, self.alto)
        rect_actual = pygame.Rect(self.x, self.y, ancho_actual, self.alto)

        # 4. Paleta de colores más moderna (código RGB)
        ratio = self.vida_actual / self.vida_maxima
        color_vida = (46, 204, 113)      # Verde esmeralda
        if ratio <= 0.5:
            color_vida = (241, 196, 15)  # Amarillo mostaza
        if ratio <= 0.2:
            color_vida = (231, 76, 60)   # Rojo carmesí

        # 5. Dibujar en capas usando border_radius para las esquinas redondeadas
        
        # Capa 1: Fondo oscuro (hueco vacío)
        pygame.draw.rect(superficie, (40, 40, 40), rect_fondo, border_radius=6)
        
        # Capa 2: Barra de daño residual (rojo claro/rosado que se queda atrás)
        pygame.draw.rect(superficie, (255, 100, 100), rect_animado, border_radius=6)
        
        # Capa 3: Barra de vida real que cambia de color
        pygame.draw.rect(superficie, color_vida, rect_actual, border_radius=6)
        
        # Capa 4: Borde exterior (grosor de 2 píxeles)
        pygame.draw.rect(superficie, (200, 200, 200), rect_fondo, width=2, border_radius=6)


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

# Crear una instancia de la barra de vida para el jugador
# Posición (10, 10), 200px de ancho, 25px de alto, 100 de vida máxima
barra_jugador = BarraVida(10, 10, 200, 25, 100)

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

     # Dibujar la barra de vida
    barra_jugador.dibujar(screen)


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
