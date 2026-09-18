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

SHOT_COOLDOWN_MS = 1000 
last_shot_time = 0


DPULGARARRIBA = 1
DPULGARABAJO = 0.5
DMENIQUEARRIBA = 1.4
DINDICEARRIBA = 1.6

pygame.init()

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Dianas")
pygame.mouse.set_visible(False)

clock = pygame.time.Clock()

BACKGROUND_IMAGE = "media/Valle.jpg"

try:
    background = pygame.image.load(BACKGROUND_IMAGE).convert()
    background = pygame.transform.scale(
        background,
        (WIDTH, HEIGHT)
    )
except:
    background = pygame.Surface((WIDTH, HEIGHT))
    background.fill((50, 80, 120))

font = pygame.font.Font(None, 36)
font_menu = pygame.font.Font(None, 72) 

PAUSE_IMAGE = "media/pause.png"
try:
    pause_sprite = pygame.image.load(PAUSE_IMAGE).convert_alpha()
except Exception as e:
    pause_sprite = None

# =========================================================
# FUNCIÓN DE DESENFOQUE (BLUR)
# =========================================================
def capturar_y_desenfocar(superficie_origen, factor=6):
    ancho = superficie_origen.get_width()
    alto = superficie_origen.get_height()
    
    pequena = pygame.transform.smoothscale(superficie_origen, (ancho // factor, alto // factor))
    desenfocada = pygame.transform.smoothscale(pequena, (ancho, alto))
    
    capa_oscura = pygame.Surface((ancho, alto))
    capa_oscura.set_alpha(150)
    capa_oscura.fill((0, 0, 0))
    
    desenfocada.blit(capa_oscura, (0, 0))
    return desenfocada

# =========================================================
# VARIABLES COMPARTIDAS ENTRE HILOS
# =========================================================

running = True
trigger_gesture = False
stop_gesture = False

hand_x = 0
hand_y = 0

lock = threading.Lock()


# =========================================================
# DIANAS
# =========================================================

TARGET_RADIUS = 40
targets = []

MAX_TARGETS = 8          
SPAWN_INTERVAL_MS = 4000 
TARGET_LIFETIME_MS = 10000  
PENALTY_DAMAGE = 5        


def crear_diana():
    return {
        "x": random.randint(TARGET_RADIUS, WIDTH - TARGET_RADIUS),
        "y": random.randint(TARGET_RADIUS + 60, HEIGHT - TARGET_RADIUS),
        "spawn_time": pygame.time.get_ticks()
    }

TARGET_IMAGE = "media/Soldier.png"
try:
    target_sprite = pygame.image.load(TARGET_IMAGE).convert_alpha()
    target_sprite = pygame.transform.scale(target_sprite,(TARGET_RADIUS * 2, TARGET_RADIUS * 2))
except Exception as e:
    target_sprite = None

EFFECT_DURATION_MS = 600
effects = []  
EXPIRE_SOUND_FILE = "media/expire.wav"
expire_sound = None
try:
    pygame.mixer.init()
    expire_sound = pygame.mixer.Sound(EXPIRE_SOUND_FILE)
except Exception as e:
    expire_sound = None

HAND_IMAGE = "media/crosshair.png"
HAND_SIZE = (40, 40)
try:
    hand_sprite = pygame.image.load(HAND_IMAGE).convert_alpha()
    hand_sprite = pygame.transform.scale(hand_sprite, HAND_SIZE)
except Exception as e:
    hand_sprite = None

for _ in range(2):
    targets.append(crear_diana())

SPAWN_EVENT = pygame.USEREVENT + 1
pygame.time.set_timer(SPAWN_EVENT, SPAWN_INTERVAL_MS)


def dibujar_diana(x, y):
    if target_sprite:
        rect = target_sprite.get_rect(center=(x, y))
        screen.blit(target_sprite, rect)
        return

    pygame.draw.circle(screen, (220, 220, 220), (x, y), TARGET_RADIUS)
    pygame.draw.circle(screen, (200, 40, 40), (x, y), int(TARGET_RADIUS * 0.75))
    pygame.draw.circle(screen, (245, 245, 245), (x, y), int(TARGET_RADIUS * 0.50))
    pygame.draw.circle(screen, (220, 40, 40), (x, y), int(TARGET_RADIUS * 0.25))


# =========================================================
# PUNTUACIÓN Y DETECCIÓN
# =========================================================

def calcular_puntuacion(x, y, diana):
    distancia = math.hypot(x - diana["x"], y - diana["y"])
    if distancia > TARGET_RADIUS: return 0
    puntuacion = int(100 * (1 - distancia / TARGET_RADIUS))
    return max(10, puntuacion)

def calcularDistancia(p1x, p1y, p2x, p2y):
    return math.hypot(p1x - p2x, p1y - p2y)


def pulgar_abierto(hand_landmarks) -> bool:
    thumb_up = False
    lm = hand_landmarks.landmark
    thumb_tip = lm[4]
    index_tip = lm[8]
    wrist = lm[0]
    middle_mcp = lm[9]

    d_thumb_index = calcularDistancia(thumb_tip.x,thumb_tip.y,index_tip.x, index_tip.y)
    hand_size = calcularDistancia(wrist.x,wrist.y,middle_mcp.x,middle_mcp.y)
    d_relativa = d_thumb_index / hand_size

    if d_relativa < DPULGARARRIBA :
        thumb_up = True
    return thumb_up


def palma_abierta(hand_landmarks) -> bool:
    open_palm = False
    lm = hand_landmarks.landmark
    thumb_tip = lm[4]
    index_tip = lm[8]
    pinky_tip = lm[20]
    wrist = lm[0]
    middle_mcp = lm[9]

    d_thumb_wrist = calcularDistancia(thumb_tip.x,thumb_tip.y,wrist.x, wrist.y)
    d_pinky_wrist = calcularDistancia(pinky_tip.x,pinky_tip.y, wrist.x, wrist.y)
    d_index_wrist = calcularDistancia(index_tip.x,index_tip.y, wrist.x, wrist.y)

    hand_size = calcularDistancia(wrist.x,wrist.y,middle_mcp.x,middle_mcp.y)

    d_thumb_wrist = d_thumb_wrist / hand_size
    d_pinky_wrist = d_pinky_wrist / hand_size
    d_index_wrist = d_index_wrist / hand_size

    if d_thumb_wrist > DPULGARARRIBA and d_pinky_wrist > DMENIQUEARRIBA and d_index_wrist > DINDICEARRIBA :
        open_palm = True
    return open_palm
               
# =========================================================
# HILO DE MEDIAPIPE + OPENCV
# =========================================================

def camara_thread():
    global running, hand_x, hand_y, trigger_gesture, stop_gesture, last_shot_time

    mp_drawing = mp.solutions.drawing_utils
    mp_hands = mp.solutions.hands

    gesture_buffer = []
    BUFFER_SIZE = 4
    gatillo_activo = False 

    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)

    with mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=2,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5
    ) as hands:
        while running:
            ret, frame = cap.read()
            if not ret: break

            frame = cv2.flip(frame, 1)
            frame_rgb = cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)
            results = hands.process(frame_rgb)

            if results.multi_hand_landmarks:
                hand = results.multi_hand_landmarks[0]
                index_finger = hand.landmark[8]

                stop_gesture_local = palma_abierta(hand) 
                trigger_gesture_local = pulgar_abierto(hand) 

                if stop_gesture_local:
                    gesto_raw = "stop"
                elif trigger_gesture_local:
                    gesto_raw = "trigger"
                else:
                    gesto_raw = "none"

                gesture_buffer.append(gesto_raw)
                if len(gesture_buffer) > BUFFER_SIZE:
                    gesture_buffer.pop(0)

                if len(gesture_buffer) == BUFFER_SIZE and gesture_buffer.count(gesture_buffer[0]) == BUFFER_SIZE:
                    gesto_confirmado = gesture_buffer[0]
                else:
                    gesto_confirmado = None  
                                    
                height, width, _ = frame.shape
                pygame_x = int(index_finger.x * WIDTH)
                pygame_y = int(index_finger.y * HEIGHT)
                current_time = pygame.time.get_ticks()

                with lock:
                    hand_x = pygame_x
                    hand_y = pygame_y

                    if gesto_confirmado == "trigger": 
                        if not gatillo_activo and (current_time - last_shot_time >= SHOT_COOLDOWN_MS):
                            trigger_gesture = True
                            stop_gesture = False
                            last_shot_time = current_time
                            gatillo_activo = True 
                        else:
                            trigger_gesture = False 
                    elif gesto_confirmado == "stop":
                        trigger_gesture = False
                        stop_gesture = True
                        gatillo_activo = False 
                    elif gesto_confirmado == "none":
                        trigger_gesture = False
                        stop_gesture = False
                        gatillo_activo = False 

                for hand_landmarks in results.multi_hand_landmarks:
                    mp_drawing.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)

            cv2.imshow("Camara - MediaPipe", frame)
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
        self.vida_animada = vida_maxima 

    def recibir_dano(self, cantidad):
        self.vida_actual = max(self.vida_actual - cantidad, 0)

    def curar(self, cantidad):
        self.vida_actual = min(self.vida_actual + cantidad, self.vida_maxima)

    def dibujar(self, superficie):
        self.vida_animada += (self.vida_actual - self.vida_animada) * 0.1
        ancho_actual = (self.vida_actual / self.vida_maxima) * self.ancho
        ancho_animado = (self.vida_animada / self.vida_maxima) * self.ancho

        rect_fondo = pygame.Rect(self.x, self.y, self.ancho, self.alto)
        rect_animado = pygame.Rect(self.x, self.y, ancho_animado, self.alto)
        rect_actual = pygame.Rect(self.x, self.y, ancho_actual, self.alto)

        ratio = self.vida_actual / self.vida_maxima
        color_vida = (46, 204, 113)      
        if ratio <= 0.5: color_vida = (241, 196, 15)  
        if ratio <= 0.2: color_vida = (231, 76, 60)   

        pygame.draw.rect(superficie, (40, 40, 40), rect_fondo, border_radius=6)
        pygame.draw.rect(superficie, (255, 100, 100), rect_animado, border_radius=6)
        pygame.draw.rect(superficie, color_vida, rect_actual, border_radius=6)
        pygame.draw.rect(superficie, (200, 200, 200), rect_fondo, width=2, border_radius=6)


# ==========================================
# CLASE MIRA ENCAPSULADA
# ==========================================
class Mira:
    def __init__(self, ruta_imagen, tamaño=(50, 50)):
        try:
            self.blanca = pygame.image.load(ruta_imagen).convert_alpha()
            self.blanca = pygame.transform.scale(self.blanca, tamaño)
        except FileNotFoundError:
            self.blanca = pygame.Surface(tamaño, pygame.SRCALPHA)
            centro = (tamaño[0]//2, tamaño[1]//2)
            pygame.draw.circle(self.blanca, (255, 255, 255), centro, 20, 2)
            pygame.draw.line(self.blanca, (255, 255, 255), (centro[0], 0), (centro[0], tamaño[1]), 2)
            pygame.draw.line(self.blanca, (255, 255, 255), (0, centro[1]), (tamaño[0], centro[1]), 2)

        self.roja = self.blanca.copy()
        self.roja.fill((255, 0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        self.disparando = False

    def procesar_evento(self, evento):
        if evento.type == pygame.MOUSEBUTTONDOWN and evento.button == 1:
            self.disparando = True
        elif evento.type == pygame.MOUSEBUTTONUP and evento.button == 1:
            self.disparando = False

    def dibujar(self, superficie, pos=None):
        imagen_actual = self.roja if self.disparando else self.blanca
        if pos is None: pos = pygame.mouse.get_pos()
        rect_mira = imagen_actual.get_rect(center=pos)
        superficie.blit(imagen_actual, rect_mira)


# =========================================================
# CREAR HILO DE CÁMARA
# =========================================================
thread_camera = threading.Thread(target=camara_thread)
thread_camera.daemon = True
thread_camera.start()


# =========================================================
# INICIALIZACIÓN BUCLE PRINCIPAL
# =========================================================
barra_jugador = BarraVida((WIDTH/2)-150, HEIGHT-50, 300, 25, 100)
mira = Mira("media/crosshair.png", tamaño=(40, 40))
puntuacion_total = 0

# Variables de Control de Estados (Pausa y Game Over)
game_paused = False
pause_background = None
pause_start_time = 0
pause_cooldown = 1000      
last_pause_toggle = 0

game_over = False
game_over_background = None
game_over_start_time = 0


while running:
    current_time = pygame.time.get_ticks()

    # Sincronización con el hilo de la cámara
    with lock:
        current_hand_x = hand_x
        current_hand_y = hand_y
        current_trigger = trigger_gesture
        current_stop = stop_gesture


    # =====================================================
    # TRANSICIONES DE ESTADO (GAME OVER Y PAUSA)
    # =====================================================
    
    # 0. DETECTAR GAME OVER
    if not game_over and barra_jugador.vida_actual <= 0:
        game_over = True
        # Capturamos la pantalla final justo antes de morir para usarla de fondo
        game_over_background = capturar_y_desenfocar(screen)
        game_over_start_time = current_time

    # 1. ENTRAR EN PAUSA (Si no estamos muertos)
    if not game_over and current_stop and not game_paused and (current_time - last_pause_toggle > pause_cooldown):
        game_paused = True
        pause_background = capturar_y_desenfocar(screen) 
        pause_start_time = current_time
        last_pause_toggle = current_time
        
    # 2. SALIR DE PAUSA
    elif not game_over and current_trigger and game_paused and (current_time - last_pause_toggle > pause_cooldown):
        game_paused = False
        time_paused = current_time - pause_start_time
        
        for diana in targets:
            diana["spawn_time"] += time_paused
        for eff in effects:
            eff["start_time"] += time_paused
            
        with lock:
            last_shot_time += time_paused
            
        last_pause_toggle = current_time
        current_trigger = False 


    # =====================================================
    # EVENTOS DE PYGAME
    # =====================================================
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        if not game_paused and not game_over: 
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mouse_x, mouse_y = pygame.mouse.get_pos()
                for diana in targets[:]:
                    distancia = math.hypot(mouse_x - diana["x"], mouse_y - diana["y"])
                    if distancia <= TARGET_RADIUS:
                        puntuacion_total += calcular_puntuacion(mouse_x, mouse_y, diana)
                        targets.remove(diana)
                        break
            elif event.type == SPAWN_EVENT:
                if len(targets) < MAX_TARGETS:
                    targets.append(crear_diana())


    # =====================================================
    # RENDERIZADO SEGÚN ESTADO (GAME OVER / PAUSA / JUEGO)
    # =====================================================
    
    if game_over:
        # -------------------------------------------------
        # ESTADO: GAME OVER
        # -------------------------------------------------
        screen.blit(game_over_background, (0, 0))
        
        # Texto principal en rojo
        txt_go = font_menu.render("GAME OVER", True, (255, 50, 50))
        rect_go = txt_go.get_rect(center=(WIDTH//2, HEIGHT//2 - 30))
        screen.blit(txt_go, rect_go)
        
        # Texto de puntuación final
        txt_puntos = font.render(f"Puntuación final: {puntuacion_total}", True, (255, 255, 255))
        rect_puntos = txt_puntos.get_rect(center=(WIDTH//2, HEIGHT//2 + 40))
        screen.blit(txt_puntos, rect_puntos)
        
        # Cerrar automáticamente a los 3 segundos
        if current_time - game_over_start_time >= 3000:
            running = False

    elif game_paused:
        # -------------------------------------------------
        # ESTADO: MENÚ DE PAUSA
        # -------------------------------------------------
        screen.blit(pause_background, (0, 0))
        
        if pause_sprite:
            rect = pause_sprite.get_rect(center=(WIDTH//2, HEIGHT//2 - 50))
            screen.blit(pause_sprite, rect)
        else:
            txt_pausa = font_menu.render("JUEGO PAUSADO", True, (255, 255, 255))
            screen.blit(txt_pausa, txt_pausa.get_rect(center=(WIDTH//2, HEIGHT//2 - 50)))
            
        txt_instruccion = font.render("Haz el gesto DISPARAR para reanudar", True, (200, 200, 200))
        screen.blit(txt_instruccion, txt_instruccion.get_rect(center=(WIDTH//2, HEIGHT//2 + 50)))

    else:
        # -------------------------------------------------
        # ESTADO: JUEGO ACTIVO
        # -------------------------------------------------
        for diana in targets[:]:
            distancia = math.hypot(current_hand_x - diana["x"], current_hand_y - diana["y"])
            if distancia <= TARGET_RADIUS and current_trigger: 
                puntos = calcular_puntuacion(current_hand_x, current_hand_y, diana)
                puntuacion_total += puntos
                targets.remove(diana)
                break

        if current_trigger:
            current_trigger = False 

        for diana in targets[:]:
            spawn = diana.get("spawn_time", 0)
            if current_time - spawn >= TARGET_LIFETIME_MS:
                effects.append({"x": diana["x"], "y": diana["y"], "start_time": current_time})
                if expire_sound:
                    try: expire_sound.play() 
                    except Exception: pass
                barra_jugador.recibir_dano(PENALTY_DAMAGE)
                targets.remove(diana)

        screen.blit(background, (0, 0))
        barra_jugador.dibujar(screen)

        for diana in targets:
            dibujar_diana(diana["x"], diana["y"])

        for eff in effects[:]:
            elapsed = current_time - eff["start_time"]
            if elapsed >= EFFECT_DURATION_MS:
                effects.remove(eff)
                continue
            t = elapsed / EFFECT_DURATION_MS
            radius = int((TARGET_RADIUS * 2.5) * t) + 5
            alpha = int(255 * (1 - t))
            surf = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(surf, (255, 100, 100, alpha), (radius, radius), radius)
            screen.blit(surf, (eff["x"] - radius, eff["y"] - radius))

        screen.blit(font.render(f"Puntuación: {puntuacion_total}", True, (255, 255, 255)), (20, 20))
        screen.blit(font.render(f"Apuntando: ({current_hand_x}, {current_hand_y})", True, (255, 255, 255)), (20, 55))


    # =====================================================
    # DIBUJAR MIRA (Siempre visible)
    # =====================================================
    pointer_pos = None
    if current_hand_x != 0 and current_hand_y != 0:
        pointer_pos = (current_hand_x, current_hand_y)
    mira.dibujar(screen, pointer_pos)

    pygame.display.flip()
    clock.tick(60)


# =========================================================
# FINALIZAR
# =========================================================
running = False
thread_camera.join(timeout=1)
pygame.quit()
cv2.destroyAllWindows()