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

SHOT_COOLDOWN_MS = 00 #para que el sonido de disparo se reproduzca bien
last_shot_time = 0


DPULGARARRIBA = 1
DPULGARABAJO = 0.5
DMENIQUEARRIBA = 1.4
DINDICEARRIBA = 1.6
DMEDIOARRIBA = 1.5
DANULARARRIBA = 1.5

pygame.init()

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Dianas")
# Ocultar el cursor del sistema: usaremos la mira/puntero dibujado por el juego
pygame.mouse.set_visible(False)

clock = pygame.time.Clock()

BACKGROUND_IMAGE = "media/Valle.jpg"

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

# Spawn settings (campo de tiro tipo Valorant)
MAX_TARGETS = 8          # máximas dianas simultáneas
SPAWN_INTERVAL_MS = 4000 # intervalo en ms entre apariciones
TARGET_LIFETIME_MS = 10000  # tiempo en ms antes de que una diana penalice si no es alcanzada
PENALTY_DAMAGE = 5        # daño aplicado si la diana expira


def crear_diana():
    return {
        "x": random.randint(
            TARGET_RADIUS,
            WIDTH - TARGET_RADIUS
        ),
        "y": random.randint(
            TARGET_RADIUS + 60,
            HEIGHT - TARGET_RADIUS
        ),
        "spawn_time": pygame.time.get_ticks()
    }

# Sprite de diana (puedes cambiar el nombre del archivo PNG)
TARGET_IMAGE = "media/Soldier.png"
try:
    target_sprite = pygame.image.load(TARGET_IMAGE).convert_alpha()
    # Escalar al tamaño del radio objetivo (diámetro)
    target_sprite = pygame.transform.scale(target_sprite,(TARGET_RADIUS * 2, TARGET_RADIUS * 2))
    print(f"Sprite de diana cargado: {TARGET_IMAGE}")
except Exception as e:
    print(f"No se pudo cargar '{TARGET_IMAGE}': {e}. Usando diana dibujada por código.")
    target_sprite = None

# Efectos y sonido al expirar dianas
EFFECT_DURATION_MS = 600
effects = []  # lista de efectos activos: dicts con x,y,start_time
EXPIRE_SOUND_FILE = "media/expire.wav"
expire_sound = None
try:
    pygame.mixer.init()
    expire_sound = pygame.mixer.Sound(EXPIRE_SOUND_FILE)
    print(f"Sonido de expiración cargado: {EXPIRE_SOUND_FILE}")
except Exception as e:
    expire_sound = None
    print(f"No se pudo cargar sonido '{EXPIRE_SOUND_FILE}': {e}. Continuando sin sonido.")

# Sprite del puntero de la mano (usa media/hand.png por defecto)
HAND_IMAGE = "media/crosshair.png"
HAND_SIZE = (40, 40)
try:
    hand_sprite = pygame.image.load(HAND_IMAGE).convert_alpha()
    hand_sprite = pygame.transform.scale(hand_sprite, HAND_SIZE)
    print(f"Sprite de mano cargado: {HAND_IMAGE}")
except Exception as e:
    hand_sprite = None
    print(f"No se pudo cargar '{HAND_IMAGE}': {e}. Usando puntero por código.")

# Inicialmente dejamos unas pocas dianas para empezar
for _ in range(2):
    targets.append(crear_diana())

# Evento de spawn periódico
SPAWN_EVENT = pygame.USEREVENT + 1
pygame.time.set_timer(SPAWN_EVENT, SPAWN_INTERVAL_MS)


def dibujar_diana(x, y):
    # Si hay un sprite cargado, lo usamos (centrado en x,y)
    if target_sprite:
        rect = target_sprite.get_rect(center=(x, y))
        screen.blit(target_sprite, rect)
        return

    # Fallback: dibujar diana con círculos si falta el sprite
    pygame.draw.circle(
        screen,
        (220, 220, 220),
        (x, y),
        TARGET_RADIUS
    )

    pygame.draw.circle(
        screen,
        (200, 40, 40),
        (x, y),
        int(TARGET_RADIUS * 0.75)
    )

    pygame.draw.circle(
        screen,
        (245, 245, 245),
        (x, y),
        int(TARGET_RADIUS * 0.50)
    )

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
    #print(d_relativa)

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

    # Punta del corazón
    middle_tip = lm[12]

    # Punta del anular
    ring_tip = lm[16]

    # Referencia para normalizar el tamaño de la mano
    wrist = lm[0]
    middle_mcp = lm[9]

    # calculamos la posicion del pulgar
    d_thumb_wrist = calcularDistancia(thumb_tip.x,thumb_tip.y,wrist.x, wrist.y)
    d_pinky_wrist = calcularDistancia(pinky_tip.x,pinky_tip.y, wrist.x, wrist.y)
    d_index_wrist = calcularDistancia(index_tip.x,index_tip.y, wrist.x, wrist.y)
    d_middle_wrist = calcularDistancia(middle_tip.x, middle_tip.y, wrist.x, wrist.y)
    d_ring_wrist = calcularDistancia(ring_tip.x, ring_tip.y, wrist.x, wrist.y)
    
    # Tamaño de la mano
    hand_size = calcularDistancia(wrist.x,wrist.y,middle_mcp.x,middle_mcp.y)

        # Distancia relativa
    d_thumb_wrist = d_thumb_wrist / hand_size
    d_pinky_wrist = d_pinky_wrist / hand_size
    d_index_wrist = d_index_wrist / hand_size
    d_middle_wrist = d_middle_wrist / hand_size
    d_ring_wrist = d_ring_wrist / hand_size


    #print("pulgar:")
    #print(d_thumb_wrist)
    #print("meñique:")
    #print(d_pinky_wrist)
    #print("indice:")
    #print(d_index_wrist)

    if d_thumb_wrist > DPULGARARRIBA and d_pinky_wrist > DMENIQUEARRIBA and d_index_wrist > DINDICEARRIBA and d_ring_wrist > DANULARARRIBA and d_middle_wrist > DMEDIOARRIBA  :
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

    global last_shot_time
     

    mp_drawing = mp.solutions.drawing_utils
    mp_hands = mp.solutions.hands

    gesture_buffer = []
    BUFFER_SIZE = 4

    gatillo_activo = False  #controla si se levanta el gatillo para no disparar continuamente
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)

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

                stop_gesture_local = palma_abierta(hand) #Comprobamos si hay stop

                trigger_gesture_local =  pulgar_abierto(hand) #Comprobamos si hay disparo


                # 2. Exclusión mutua -> un solo gesto "crudo" para este frame
                if stop_gesture_local:
                    gesto_raw = "stop"
                elif trigger_gesture_local:
                    gesto_raw = "trigger"
                else:
                    gesto_raw = "none"

                # 3. Meter en el buffer de debounce
                gesture_buffer.append(gesto_raw)
                if len(gesture_buffer) > BUFFER_SIZE:
                    gesture_buffer.pop(0)

                # 4. Confirmar solo si TODO el buffer coincide
                if len(gesture_buffer) == BUFFER_SIZE and gesture_buffer.count(gesture_buffer[0]) == BUFFER_SIZE:
                    gesto_confirmado = gesture_buffer[0]
                else:
                    gesto_confirmado = None  # aún no hay consenso, no cambiamos nada
                                    
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

                current_time = pygame.time.get_ticks()


                # Guardar coordenadas de forma segura
                with lock:
                    hand_x = pygame_x
                    hand_y = pygame_y

                    if gesto_confirmado == "trigger": 
                        if not gatillo_activo and (current_time - last_shot_time >= SHOT_COOLDOWN_MS):
                            trigger_gesture = True
                            stop_gesture = False
                            last_shot_time = current_time
                            gatillo_activo = True #el gatillo está activo despues de una bala: no disparar
                        else:
                            trigger_gesture = False 
                    elif gesto_confirmado == "stop":
                        trigger_gesture = False
                        stop_gesture = True
                        gatillo_activo = False 
                    elif gesto_confirmado == "none":
                        trigger_gesture = False
                        stop_gesture = False
                        gatillo_activo = False #se suelte el gatillo
                    

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

# ==========================================
# CLASE MIRA ENCAPSULADA
# ==========================================
class Mira:
    def __init__(self, ruta_imagen, tamaño=(50, 50)):
        # Procesar evento para la mira (clase Mira)
        try:
            mira.procesar_evento(event)
        except NameError:
            pass
        # 1. Cargar la imagen blanca
        try:
            self.blanca = pygame.image.load(ruta_imagen).convert_alpha()
            self.blanca = pygame.transform.scale(self.blanca, tamaño)
        except FileNotFoundError:
            # Respaldo si no encuentra el archivo
            self.blanca = pygame.Surface(tamaño, pygame.SRCALPHA)
            centro = (tamaño[0]//2, tamaño[1]//2)
            pygame.draw.circle(self.blanca, (255, 255, 255), centro, 20, 2)
            pygame.draw.line(self.blanca, (255, 255, 255), (centro[0], 0), (centro[0], tamaño[1]), 2)
            pygame.draw.line(self.blanca, (255, 255, 255), (0, centro[1]), (tamaño[0], centro[1]), 2)

        # 2. Generar automáticamente la versión roja
        self.roja = self.blanca.copy()
        self.roja.fill((255, 0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        
        # 3. Estado de la mira
        self.disparando = False

    def procesar_evento(self, evento):
        # Actualizar el estado si se hace clic
        if evento.type == pygame.MOUSEBUTTONDOWN and evento.button == 1:
            self.disparando = True
        elif evento.type == pygame.MOUSEBUTTONUP and evento.button == 1:
            self.disparando = False

    def dibujar(self, superficie, pos=None):
        # Elegir la imagen según el estado
        imagen_actual = self.roja if self.disparando else self.blanca

        # Si se pasa `pos`, la usamos (por ejemplo la posición de la mano),
        # si no, usamos la posición del ratón.
        if pos is None:
            pos = pygame.mouse.get_pos()

        rect_mira = imagen_actual.get_rect(center=pos)
        superficie.blit(imagen_actual, rect_mira)
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
# Posición (WIDTH/2, HEIGHT-100), 200px de ancho, 25px de alto, 100 de vida máxima

barra_jugador = BarraVida((WIDTH/2)-150, HEIGHT-50, 300, 25, 100)
mira = Mira("media/crosshair.png", tamaño=(40, 40))
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
        # Evento periódico para generar nuevas dianas
        elif event.type == SPAWN_EVENT:
            if len(targets) < MAX_TARGETS:
                targets.append(crear_diana())




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

        

        distancia = math.hypot(
            current_hand_x - diana["x"],
            current_hand_y - diana["y"]
        )

        if distancia <= TARGET_RADIUS and current_trigger: #si las posiciones coinciden y ejecutar el trigger:
            
            puntos = calcular_puntuacion(
                current_hand_x,
                current_hand_y,
                diana
            )

            puntuacion_total += puntos

            targets.remove(diana)

            break

        if current_stop :
            print("Stop")
        if current_trigger :
            print("Disparo")
            current_trigger = False


    # =====================================================
    # COMPROBAR Dianas expirada -> penalizar vida
    # =====================================================
    current_time = pygame.time.get_ticks()
    for diana in targets[:]:
        spawn = diana.get("spawn_time", 0)
        if current_time - spawn >= TARGET_LIFETIME_MS:
            # Añadir efecto visual y reproducir sonido
            effects.append({
                "x": diana["x"],
                "y": diana["y"],
                "start_time": current_time
            })
            if expire_sound:
                try:
                    expire_sound.play()
                except Exception:
                    pass

            print(f"Diana en ({diana['x']}, {diana['y']}) ha expirado. -{PENALTY_DAMAGE} vida")
            barra_jugador.recibir_dano(PENALTY_DAMAGE)
            targets.remove(diana)


    # =====================================================
    # FONDO
    # =====================================================

    screen.blit(
        background,
        (0, 0)
    )
    # Dibujar la barra de vida
    barra_jugador.dibujar(screen)


    # =====================================================
    # DIANAS
    # =====================================================

    for diana in targets:

        dibujar_diana(
            diana["x"],
            diana["y"]
        )

    # Dibujar efectos (fade/expand) de expiración
    now = pygame.time.get_ticks()
    for eff in effects[:]:
        elapsed = now - eff["start_time"]
        if elapsed >= EFFECT_DURATION_MS:
            effects.remove(eff)
            continue

        t = elapsed / EFFECT_DURATION_MS
        max_radius = TARGET_RADIUS * 2.5
        radius = int(max_radius * t) + 5
        alpha = int(255 * (1 - t))

        diameter = radius * 2
        surf = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
        color = (255, 100, 100, alpha)
        pygame.draw.circle(surf, color, (radius, radius), radius)

        screen.blit(surf, (eff["x"] - radius, eff["y"] - radius))


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

    # Determinar posición del puntero: preferimos la mano si está disponible
    pointer_pos = None
    if current_hand_x != 0 and current_hand_y != 0:
        pointer_pos = (current_hand_x, current_hand_y)

    # Dibujar la mira (usa la clase `Mira` definida arriba) en la posición calculada
    try:
        mira.dibujar(screen, pointer_pos)
    except NameError:
        pass



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