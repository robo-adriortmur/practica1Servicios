import pygame
import random
import math
import mediapipe as mp
import cv2
import threading
import time

# =========================================================
# CONFIGURACIÓN DEL JUEGO
# =========================================================
WIDTH = 850
HEIGHT = 600

TARGET_RADIUS = 40
MAX_TARGETS = 8          
SPAWN_INTERVAL_MS = 4000   # Mitad de velocidad (antes 2000)
TARGET_LIFETIME_MS = 10000 # 10 segundos antes de expirar (antes 6000)
PENALTY_DAMAGE = 5

pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Juego: Disparo, Inventario y Pausa")
pygame.mouse.set_visible(False)
clock = pygame.time.Clock()

font = pygame.font.Font(None, 36)
font_menu = pygame.font.Font(None, 72) 

# Carga de recursos
try: background = pygame.transform.scale(pygame.image.load("media/Valle.jpg").convert(), (WIDTH, HEIGHT))
except: background = pygame.Surface((WIDTH, HEIGHT)); background.fill((50, 80, 120))

try: pause_sprite = pygame.image.load("media/pause.png").convert_alpha()
except: pause_sprite = None

try:
    target_sprite = pygame.image.load("media/Soldier.png").convert_alpha()
    target_sprite = pygame.transform.scale(target_sprite,(TARGET_RADIUS * 2, TARGET_RADIUS * 2))
except: target_sprite = None

# Inicializar sistema de audio y cargar sonidos
try:
    pygame.mixer.init()
except:
    pass

try: expire_sound = pygame.mixer.Sound("media/expire.wav")
except: expire_sound = None

try: shoot_sound = pygame.mixer.Sound("media/pistola.mp3")
except: shoot_sound = None

# =========================================================
# VARIABLES COMPARTIDAS (HILOS)
# =========================================================
lock = threading.Lock()
running = True

# Coordenadas y acciones (Cámara -> Pygame)
hand_x, hand_y = 0, 0
trigger_shoot = False
trigger_pause = False
trigger_unpause = False

# Estado del juego (Pygame -> Cámara)
game_paused = False

# =========================================================
# FUNCIONES AUXILIARES Y CLASES
# =========================================================
def calcular_distancia(punto1, punto2):
    return math.hypot(punto1.x - punto2.x, punto1.y - punto2.y)

def capturar_y_desenfocar(superficie_origen, factor=6):
    ancho, alto = superficie_origen.get_width(), superficie_origen.get_height()
    pequena = pygame.transform.smoothscale(superficie_origen, (ancho // factor, alto // factor))
    desenfocada = pygame.transform.smoothscale(pequena, (ancho, alto))
    capa_oscura = pygame.Surface((ancho, alto))
    capa_oscura.set_alpha(150)
    desenfocada.blit(capa_oscura, (0, 0))
    return desenfocada

class BarraVida:
    def __init__(self, x, y, ancho, alto, vida_maxima):
        self.rect_base = pygame.Rect(x, y, ancho, alto)
        self.vida_maxima = vida_maxima
        self.vida_actual = vida_maxima
        self.vida_animada = vida_maxima 

    def recibir_dano(self, cantidad):
        self.vida_actual = max(self.vida_actual - cantidad, 0)

    def dibujar(self, superficie):
        self.vida_animada += (self.vida_actual - self.vida_animada) * 0.1
        w_actual = (self.vida_actual / self.vida_maxima) * self.rect_base.width
        w_animado = (self.vida_animada / self.vida_maxima) * self.rect_base.width

        color = (46, 204, 113)      
        if self.vida_actual / self.vida_maxima <= 0.5: color = (241, 196, 15)  
        if self.vida_actual / self.vida_maxima <= 0.2: color = (231, 76, 60)   

        pygame.draw.rect(superficie, (40, 40, 40), self.rect_base, border_radius=6)
        pygame.draw.rect(superficie, (255, 100, 100), (self.rect_base.x, self.rect_base.y, w_animado, self.rect_base.height), border_radius=6)
        pygame.draw.rect(superficie, color, (self.rect_base.x, self.rect_base.y, w_actual, self.rect_base.height), border_radius=6)
        pygame.draw.rect(superficie, (200, 200, 200), self.rect_base, width=2, border_radius=6)

class Mira:
    def __init__(self, tamaño=(40, 40)):
        self.blanca = pygame.Surface(tamaño, pygame.SRCALPHA)
        centro = (tamaño[0]//2, tamaño[1]//2)
        pygame.draw.circle(self.blanca, (255, 255, 255), centro, 15, 2)
        pygame.draw.circle(self.blanca, (255, 0, 0), centro, 2)
        self.roja = self.blanca.copy()
        self.roja.fill((255, 0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        self.disparando = False

    def dibujar(self, superficie, pos):
        if pos:
            img = self.roja if self.disparando else self.blanca
            superficie.blit(img, img.get_rect(center=pos))

# =========================================================
# HILO DE MEDIAPIPE (GESTOS Y ESTADOS)
# =========================================================
def camara_thread():
    global running, hand_x, hand_y, trigger_shoot, trigger_pause, trigger_unpause

    mp_hands = mp.solutions.hands
    mp_drawing = mp.solutions.drawing_utils
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)

    # Variables de estado local de la cámara
    nombres_objetos = {8: "Dedo Índice", 12: "Dedo Medio", 16: "Dedo Anular", 20: "Dedo Meñique"}
    inventario_abierto = False
    estado_dedos_doblados = {8: False, 12: False, 16: False, 20: False}
    pulgar_listo_para_disparar = False
    
    tiempo_inicio_pausa = 0
    tiempo_inicio_reanudar = 0

    with mp_hands.Hands(static_image_mode=False, max_num_hands=1, min_detection_confidence=0.5, min_tracking_confidence=0.5) as hands:
        while running:
            ret, frame = cap.read()
            if not ret: break

            frame = cv2.flip(frame, 1)
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            resultados = hands.process(frame_rgb)

            with lock:
                estado_pausa = game_paused

            if resultados.multi_hand_landmarks and resultados.multi_handedness:
                mano = resultados.multi_hand_landmarks[0]
                etiqueta_mano = resultados.multi_handedness[0].classification[0].label
                mp_drawing.draw_landmarks(frame, mano, mp_hands.HAND_CONNECTIONS)
                
                puntos = mano.landmark
                muneca = puntos[0]

                # Tracking del puntero (Índice)
                with lock:
                    hand_x, hand_y = int(puntos[8].x * WIDTH), int(puntos[8].y * HEIGHT)

                # Pre-cálculo del estado de los dedos (extendidos vs cerrados)
                indice_ext = calcular_distancia(puntos[8], muneca) > calcular_distancia(puntos[6], muneca)
                medio_ext = calcular_distancia(puntos[12], muneca) > calcular_distancia(puntos[10], muneca)
                anular_ext = calcular_distancia(puntos[16], muneca) > calcular_distancia(puntos[14], muneca)
                menique_ext = calcular_distancia(puntos[20], muneca) > calcular_distancia(puntos[18], muneca)
                
                # Gestos Generales
                es_palma_abierta = indice_ext and medio_ext and anular_ext and menique_ext
                es_puno_cerrado = not (indice_ext or medio_ext or anular_ext or menique_ext)

                # ==========================================
                # LÓGICA ESTRICTA SEGÚN ESTADO DEL JUEGO
                # ==========================================
                if estado_pausa:
                    # DURANTE LA PAUSA: Solo escuchamos el puño cerrado para salir
                    cv2.putText(frame, "JUEGO PAUSADO: Mantenga puno cerrado para salir", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                    
                    if es_puno_cerrado:
                        if tiempo_inicio_reanudar == 0: tiempo_inicio_reanudar = time.time()
                        elapsed = time.time() - tiempo_inicio_reanudar
                        cv2.putText(frame, f"Reanudando... {int((elapsed/2)*100)}%", (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
                        
                        if elapsed >= 2.0:
                            print("\n[+] JUEGO REANUDADO")
                            with lock: trigger_unpause = True
                            tiempo_inicio_reanudar = 0
                    else:
                        tiempo_inicio_reanudar = 0
                
                else:
                    # JUEGO NORMAL: Verificamos Inventario primero
                    mcp_medio = puntos[9]
                    es_horizontal = abs(mcp_medio.x - muneca.x) > 1.2 * abs(mcp_medio.y - muneca.y)
                    dorso_hacia_camara = puntos[2].y < puntos[17].y

                    estado_anterior_inv = inventario_abierto
                    inventario_abierto = es_horizontal and dorso_hacia_camara

                    if inventario_abierto and not estado_anterior_inv: print("\n[+] INVENTARIO ABIERTO")
                    elif not inventario_abierto and estado_anterior_inv: print("[-] INVENTARIO CERRADO")

                    if inventario_abierto:
                        # EN INVENTARIO: Bloquea disparo y pausa
                        tiempo_inicio_pausa = 0
                        pulgar_listo_para_disparar = False
                        
                        cv2.putText(frame, "INVENTARIO ACTIVO", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                        puntas_dedos = [8, 12, 16, 20]
                        for punta_idx in puntas_dedos:
                            dedo_doblado = calcular_distancia(puntos[punta_idx], muneca) < calcular_distancia(puntos[punta_idx - 2], muneca)
                            if dedo_doblado and not estado_dedos_doblados[punta_idx]:
                                print(f"   -> Objeto tocado: {nombres_objetos[punta_idx]}")
                            estado_dedos_doblados[punta_idx] = dedo_doblado

                    else:
                        # FUERA DE INVENTARIO: Comprobar Pausa y Disparo
                        for clave in estado_dedos_doblados.keys(): estado_dedos_doblados[clave] = False

                        # 1. Detectar Pausa (Palma Abierta 2s)
                        if es_palma_abierta:
                            pulgar_listo_para_disparar = False # Cancela intento de disparo
                            if tiempo_inicio_pausa == 0: tiempo_inicio_pausa = time.time()
                            elapsed = time.time() - tiempo_inicio_pausa
                            cv2.putText(frame, f"Pausando... {int((elapsed/2)*100)}%", (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
                            
                            if elapsed >= 2.0:
                                print("\n[-] JUEGO EN PAUSA")
                                with lock: trigger_pause = True
                                tiempo_inicio_pausa = 0
                        else:
                            tiempo_inicio_pausa = 0
                            
                            # 2. Detectar Disparo (Solo si no estamos pausando)
                            es_mano_derecha = (etiqueta_mano == "Right")
                            palma_de_frente = puntos[5].x < puntos[17].x 
                            gesto_pistola = indice_ext and not medio_ext and not anular_ext and not menique_ext

                            if es_mano_derecha and palma_de_frente and gesto_pistola:
                                cv2.putText(frame, "ARMA LISTA", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 165, 255), 2)
                                pulgar_extendido = puntos[4].x < puntos[3].x
                                
                                if pulgar_extendido:
                                    pulgar_listo_para_disparar = True
                                    cv2.putText(frame, "Gatillo: Listo", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                                else:
                                    if pulgar_listo_para_disparar:
                                        print("[!] PUM! Disparo efectuado")
                                        with lock: trigger_shoot = True
                                        pulgar_listo_para_disparar = False
                                    cv2.putText(frame, "Gatillo: Apretado", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                            else:
                                pulgar_listo_para_disparar = False

            cv2.imshow("Camara - MediaPipe", frame)
            if cv2.waitKey(1) & 0xFF == 27:
                running = False
                break

    cap.release()
    cv2.destroyAllWindows()

# =========================================================
# INICIALIZACIÓN DE BUCLE PRINCIPAL
# =========================================================
thread_camera = threading.Thread(target=camara_thread)
thread_camera.daemon = True
thread_camera.start()

targets = [{"x": random.randint(TARGET_RADIUS, WIDTH - TARGET_RADIUS), "y": random.randint(TARGET_RADIUS + 60, HEIGHT - TARGET_RADIUS), "spawn_time": pygame.time.get_ticks()} for _ in range(2)]
effects = []
pygame.time.set_timer(pygame.USEREVENT + 1, SPAWN_INTERVAL_MS)

barra_jugador = BarraVida((WIDTH/2)-150, HEIGHT-50, 300, 25, 100)
mira = Mira()
puntuacion_total = 0

pause_background = None
pause_start_time = 0

while running:
    current_time = pygame.time.get_ticks()

    with lock:
        cur_hand_x, cur_hand_y = hand_x, hand_y
        local_trigger_shoot = trigger_shoot
        local_trigger_pause = trigger_pause
        local_trigger_unpause = trigger_unpause
        
        # Consumir los triggers
        if trigger_shoot: trigger_shoot = False
        if trigger_pause: trigger_pause = False
        if trigger_unpause: trigger_unpause = False

    # Reproducir sonido de pistola siempre que se apriete el gatillo
    if local_trigger_shoot:
        if shoot_sound:
            try: shoot_sound.play()
            except: pass

    # =====================================================
    # CONTROL DE ESTADOS DE PYGAME
    # =====================================================
    if barra_jugador.vida_actual <= 0:
        screen.blit(capturar_y_desenfocar(screen), (0, 0))
        txt = font_menu.render("GAME OVER", True, (255, 50, 50))
        screen.blit(txt, txt.get_rect(center=(WIDTH//2, HEIGHT//2)))
        pygame.display.flip()
        pygame.time.wait(3000)
        running = False
        continue

    # Transición a Pausa
    if local_trigger_pause and not game_paused:
        with lock: game_paused = True
        pause_background = capturar_y_desenfocar(screen)
        pause_start_time = current_time

    # Transición a Reanudar
    if local_trigger_unpause and game_paused:
        with lock: game_paused = False
        time_paused = current_time - pause_start_time
        for diana in targets: diana["spawn_time"] += time_paused
        for eff in effects: eff["start_time"] += time_paused

    # Eventos base del sistema
    for event in pygame.event.get():
        if event.type == pygame.QUIT: running = False
        elif event.type == pygame.USEREVENT + 1 and not game_paused and len(targets) < MAX_TARGETS:
            targets.append({"x": random.randint(TARGET_RADIUS, WIDTH - TARGET_RADIUS), "y": random.randint(TARGET_RADIUS + 60, HEIGHT - TARGET_RADIUS), "spawn_time": current_time})

    # =====================================================
    # RENDERIZADO
    # =====================================================
    if game_paused:
        screen.blit(pause_background, (0, 0))
        if pause_sprite: screen.blit(pause_sprite, pause_sprite.get_rect(center=(WIDTH//2, HEIGHT//2 - 50)))
        else: screen.blit(font_menu.render("PAUSA", True, (255, 255, 255)), font_menu.render("PAUSA", True, (255, 255, 255)).get_rect(center=(WIDTH//2, HEIGHT//2 - 50)))
        txt_inst = font.render("Manten el PUÑO CERRADO 2s de frente para reanudar", True, (200, 200, 200))
        screen.blit(txt_inst, txt_inst.get_rect(center=(WIDTH//2, HEIGHT//2 + 50)))
    
    else:
        # Lógica de juego normal
        for diana in targets[:]:
            distancia = math.hypot(cur_hand_x - diana["x"], cur_hand_y - diana["y"])
            # Mecánica de Disparo
            if distancia <= TARGET_RADIUS and local_trigger_shoot: 
                puntuacion_total += max(10, int(100 * (1 - distancia / TARGET_RADIUS)))
                targets.remove(diana)
                break
                
            # Expiración y daño
            elif current_time - diana["spawn_time"] >= TARGET_LIFETIME_MS:
                effects.append({"x": diana["x"], "y": diana["y"], "start_time": current_time})
                if expire_sound: 
                    try: expire_sound.play()
                    except: pass
                barra_jugador.recibir_dano(PENALTY_DAMAGE)
                targets.remove(diana)

        # Dibujado principal
        screen.blit(background, (0, 0))
        barra_jugador.dibujar(screen)

        for diana in targets:
            if target_sprite: screen.blit(target_sprite, target_sprite.get_rect(center=(diana["x"], diana["y"])))
            else: pygame.draw.circle(screen, (200, 40, 40), (diana["x"], diana["y"]), TARGET_RADIUS)

        # Efecto visual de explosión
        for eff in effects[:]:
            elapsed = current_time - eff["start_time"]
            if elapsed >= 600:
                effects.remove(eff)
                continue
            t = elapsed / 600
            r = int((TARGET_RADIUS * 2.5) * t) + 5
            surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            pygame.draw.circle(surf, (255, 50, 50, int(255 * (1 - t))), (r, r), r)
            screen.blit(surf, (eff["x"] - r, eff["y"] - r))

        screen.blit(font.render(f"Puntuación: {puntuacion_total}", True, (255, 255, 255)), (20, 20))

    # La mira siempre se actualiza por encima de todo
    mira.disparando = local_trigger_shoot
    mira.dibujar(screen, (cur_hand_x, cur_hand_y) if cur_hand_x != 0 else None)

    pygame.display.flip()
    clock.tick(60)

running = False
thread_camera.join(timeout=1)
pygame.quit()
cv2.destroyAllWindows()