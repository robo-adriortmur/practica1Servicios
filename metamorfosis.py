import pygame
import random
import math
import mediapipe as mp
import cv2
import threading
import time

# CONFIGURACIÓN DEL JUEGO
WIDTH = 850
HEIGHT = 600

# Constantes para las dianas
TARGET_RADIUS = 40
MAX_TARGETS = 8          
SPAWN_INTERVAL_MS = 4000   
TARGET_LIFETIME_MS = 10000 
PENALTY_DAMAGE = 5

# Constantes para las armas
CADENCIA_METRALLETA = 0.15
TIEMPO_RECARGA = 1.5
MAX_BALAS_PISTOLA = 6
MAX_BALAS_METRALLETA = 30


# CONSTANTES PARA RECONOCIMIENTO DE GESTOS CON DISTANCIAS ABSOLUTAS
DPULGARARRIBA = 1
DPULGARABAJO = 0.5
DMENIQUEARRIBA = 1.4
DINDICEARRIBA = 1.6
DMEDIOARRIBA = 1.5
DANULARARRIBA = 1.5

# Configuración del Inventario
KILLS_PARA_ULTI = 5
PROBABILIDAD_DROP = 0.4 # 40% de probabilidad que caiga un objeto al matar un enemigo

pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Juego: Disparo, Inventario y Pausa")
pygame.mouse.set_visible(False)
clock = pygame.time.Clock()

font = pygame.font.Font(None, 36)
font_small = pygame.font.Font(None, 24)
font_menu = pygame.font.Font(None, 72) 

# CARGA DE RECURSOS E IMÁGENES
try: background = pygame.transform.scale(pygame.image.load("media/Valle.jpg").convert(), (WIDTH, HEIGHT))
except: background = pygame.Surface((WIDTH, HEIGHT)); background.fill((50, 80, 120))

try: pause_sprite = pygame.image.load("media/pause.png").convert_alpha()
except: pause_sprite = None

try:
    target_sprite = pygame.image.load("media/Soldier.png").convert_alpha()
    target_sprite = pygame.transform.scale(target_sprite,(TARGET_RADIUS * 2, TARGET_RADIUS * 2))
except: target_sprite = None

# Sonidos
try: pygame.mixer.init()
except: pass
try: expire_sound = pygame.mixer.Sound("media/expire.wav")
except: expire_sound = None
try: shoot_sound = pygame.mixer.Sound("media/gunshot.wav")
except: shoot_sound = None
try: recharge_sound = pygame.mixer.Sound("media/recharge.wav")
except: recharge_sound = None

# Rutas preparadas para los iconos del inventario
RUTAS_INVENTARIO = {
    8: "media/MedKit.png",
    12: "media/explosive_bullet.png",
    16: "media/shield.png",
    20: "media/nuke.png"
}
imagenes_inventario = {}
for key, ruta in RUTAS_INVENTARIO.items():
    try:
        img = pygame.image.load(ruta).convert_alpha()
        imagenes_inventario[key] = pygame.transform.scale(img, (48, 48))
    except:
        imagenes_inventario[key] = None

# VARIABLES COMPARTIDAS (HILOS)
lock = threading.Lock()
running = True

# Coordenadas y acciones (Cámara -> Pygame)
hand_x, hand_y = 0, 0
trigger_shoot = False
trigger_pause = False
trigger_unpause = False
recharge_weapon = False
balas_pistola = MAX_BALAS_PISTOLA
balas_metralleta = MAX_BALAS_METRALLETA
arma_activa = "Pistola"
items_usados_buffer = []

# Estado del juego (Pygame -> Cámara)
game_paused = False

# FUNCIONES AUXILIARES Y CLASES
def calcular_distancia(punto1, punto2):
    return math.hypot(punto1.x - punto2.x, punto1.y - punto2.y)

# Detectar stop de forma absoluta
def palma_abierta_abs(hand_landmarks) -> bool:

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

    # calculamos la posicion de cada dedo con respecto a la muñeca

    d_thumb_wrist = calcular_distancia(thumb_tip, wrist) #pulgar
    d_pinky_wrist = calcular_distancia(pinky_tip, wrist) #meñique
    d_index_wrist = calcular_distancia(index_tip, wrist) #indice
    d_middle_wrist = calcular_distancia(middle_tip, wrist) #corazon
    d_ring_wrist = calcular_distancia(ring_tip, wrist) #anular
    
    #Calculamos el tamaño de la palma de la mana a traves de muñeca-puntoMedio
    hand_size = calcular_distancia(wrist,middle_mcp)

    #Distancia relativa al tamaño de la mano
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

    # Comprobamos cada lectura de distancia con lecturas previas absolutas para cualquier posición de la palma
    if d_thumb_wrist > DPULGARARRIBA and d_pinky_wrist > DMENIQUEARRIBA and d_index_wrist > DINDICEARRIBA and d_ring_wrist > DANULARARRIBA and d_middle_wrist > DMEDIOARRIBA  :
        open_palm = True

    return open_palm


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

    def curar(self, cantidad):
        self.vida_actual = min(self.vida_actual + cantidad, self.vida_maxima)

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

class HUDInventario:
    def __init__(self):
        self.ancho_slot = 60
        self.alto_slot = 60
        self.espaciado = 10
        self.ancho_total = (self.ancho_slot * 4) + (self.espaciado * 3)
        self.x_inicio = (WIDTH - self.ancho_total) // 2
        self.y_inicio = HEIGHT - 130  

    def dibujar(self, superficie, inventario, ulti_kills):
        claves = [8, 12, 16, 20]
        nombres = ["Botiquín", "Explosiva", "Escudo", "Ulti"]
        
        for i, clave in enumerate(claves):
            x_slot = self.x_inicio + i * (self.ancho_slot + self.espaciado)
            rect_slot = pygame.Rect(x_slot, self.y_inicio, self.ancho_slot, self.alto_slot)
            
            pygame.draw.rect(superficie, (139, 139, 139), rect_slot)
            pygame.draw.rect(superficie, (55, 55, 55), rect_slot, 3)
            pygame.draw.rect(superficie, (255, 255, 255), rect_slot, 1) 
            
            img = imagenes_inventario.get(clave)
            if img:
                superficie.blit(img, img.get_rect(center=rect_slot.center))
            else:
                txt_placeholder = font.render(nombres[i][0], True, (200, 200, 200))
                superficie.blit(txt_placeholder, txt_placeholder.get_rect(center=rect_slot.center))

            if clave == 20: 
                if inventario[clave] > 0:
                    txt_carga = font_small.render("LISTA", True, (0, 255, 255))
                    superficie.blit(txt_carga, (x_slot + 5, self.y_inicio + 40))
                else:
                    altura_carga = (self.alto_slot - 4) * (ulti_kills / KILLS_PARA_ULTI)
                    rect_carga = pygame.Rect(x_slot + 2, self.y_inicio + self.alto_slot - 2 - altura_carga, self.ancho_slot - 4, altura_carga)
                    pygame.draw.rect(superficie, (100, 0, 255, 100), rect_carga) 
            else:
                cantidad = inventario[clave]
                if cantidad > 0:
                    txt_cant = font_small.render(str(cantidad), True, (255, 255, 255))
                    txt_shadow = font_small.render(str(cantidad), True, (0, 0, 0))
                    superficie.blit(txt_shadow, (x_slot + self.ancho_slot - 14, self.y_inicio + self.alto_slot - 19))
                    superficie.blit(txt_cant, (x_slot + self.ancho_slot - 15, self.y_inicio + self.alto_slot - 20))

class Mira:
    def __init__(self):
        self.disparando = False
        self.explosiva = False

    def dibujar(self, superficie, pos):
        if pos:
            # Si hay munición explosiva, el radio es enorme (120), si no, normal (25)
            radio = 120 if self.explosiva else 25
            color = (255, 0, 0) if self.disparando else (255, 255, 255)
            grosor = 3 if self.explosiva else 2
            
            # Círculo principal
            pygame.draw.circle(superficie, color, pos, radio, grosor)
            
            # Líneas de la cruz
            pygame.draw.line(superficie, color, (pos[0] - radio - 5, pos[1]), (pos[0] + radio + 5, pos[1]), grosor)
            pygame.draw.line(superficie, color, (pos[0], pos[1] - radio - 5), (pos[0], pos[1] + radio + 5), grosor)
            
            # Punto rojo central siempre presente
            pygame.draw.circle(superficie, (255, 0, 0), pos, 3)

# HILO DE MEDIAPIPE (GESTOS Y ESTADOS)
def camara_thread():
    global running, hand_x, hand_y, trigger_shoot, trigger_pause, trigger_unpause

    global recharge_weapon, balas_pistola, balas_metralleta, arma_activa

    mp_hands = mp.solutions.hands
    mp_drawing = mp.solutions.drawing_utils
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)

    # Diccionario para manejar los nombres de las diferentes landmarks sintácticamente 
    nombres_objetos = {8: "Dedo Índice", 12: "Dedo Medio", 16: "Dedo Anular", 20: "Dedo Meñique"}

    
    # Diccionario para manejar el estado de los dedos usando el diccionario de nombres
    estado_dedos_doblados = {8: False, 12: False, 16: False, 20: False}

    # variables de estado locales
    inventario_abierto = False
    pulgar_listo_para_disparar = False
    listo_para_recargar = False

    tiempo_inicio_pausa = 0
    tiempo_inicio_reanudar = 0
    time_ultimo_disparo = 0
    time_ultima_recarga = 0

    tiempo_actual = 0

    #establecemos los parametros de detección de la mano
    with mp_hands.Hands(static_image_mode=False, max_num_hands=1, min_detection_confidence=0.5, min_tracking_confidence=0.5) as hands: 
        while running: # BUCLE PRINCIPAL 
            ret, frame = cap.read()
            if not ret: break

            frame = cv2.flip(frame, 1)
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            resultados = hands.process(frame_rgb)

            with lock:
                estado_pausa = game_paused

            if resultados.multi_hand_landmarks and resultados.multi_handedness: #si existen resultados de la mano los evaluamos
                mano = resultados.multi_hand_landmarks[0] #mano detectada
                etiqueta_mano = resultados.multi_handedness[0].classification[0].label
                mp_drawing.draw_landmarks(frame, mano, mp_hands.HAND_CONNECTIONS) #dibujamos los landmarks para referencia 
                
                puntos = mano.landmark 
                muneca = puntos[0] #punto de referencia de la muñeca

                with lock:
                    hand_x, hand_y = int(puntos[8].x * WIDTH), int(puntos[8].y * HEIGHT) #acotamos distancia de la mano

                #Calculamos la distancia relativa entre los puntos de la mano

                #El indice está extendido si la primera falange queda detras de la punta del mismo
                indice_ext = calcular_distancia(puntos[8], muneca) > calcular_distancia(puntos[6], muneca)

                #El dedo corazón está extendido si la primera falange del mismo queda detás de la punta
                medio_ext = calcular_distancia(puntos[12], muneca) > calcular_distancia(puntos[10], muneca)

                #Misma lógica para el anular
                anular_ext = calcular_distancia(puntos[16], muneca) > calcular_distancia(puntos[14], muneca)

                #Misma lógica para el meñique
                menique_ext = calcular_distancia(puntos[20], muneca) > calcular_distancia(puntos[18], muneca)

                #comprobamos también usando la distancia absoluta con valores precalculados
                #es_palma_abierta_abs = palma_abierta_abs(mano)

                #la palma está abierta si consideramos todos los dedos menos el pulgar extendidos
                es_palma_abierta = indice_ext and medio_ext and anular_ext and menique_ext #and es_palma_abierta_abs

                #El puño lo considereamos cerrado o semicerrado si los dedos no están extendidos
                es_puno_cerrado = not (indice_ext or medio_ext or anular_ext or menique_ext)

                if estado_pausa:
                    cv2.putText(frame, "JUEGO PAUSADO: Mantenga puno cerrado para salir", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                    if es_puno_cerrado: #comprabamos durante el estado de pausa si se ha cerrado el puño

                        if tiempo_inicio_reanudar == 0: tiempo_inicio_reanudar = time.time() #si está cerrado miramos el timer mientras el puño está cerrado
                        elapsed = time.time() - tiempo_inicio_reanudar # t_puño_cerrado para t_estado_pausa

                        #imprimimos una barra de progreso simple
                        cv2.putText(frame, f"Reanudando... {int((elapsed/2)*100)}%", (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2) 
                        
                        if elapsed >= 2.0: #si se cumple que el tiempo llega al tiempo de espera se reanuda
                            print("\n[+] JUEGO REANUDADO")
                            with lock: trigger_unpause = True #lock para el thread 
                            tiempo_inicio_reanudar = 0
                    else:
                        tiempo_inicio_reanudar = 0 
                
                else: 
                    mcp_medio = puntos[9] #punto medio de la mano

                    #usamos el punto medio y lo comparamos con la muñeca, si su posición x es mayor está lado
                    es_horizontal = abs(mcp_medio.x - muneca.x) > 1.2 * abs(mcp_medio.y - muneca.y)# el 1.2 le añade tolerancia

                    #el dorso está para arriba si el pulgar queda por encima
                    dorso_hacia_camara = puntos[2].y < puntos[17].y

                    estado_anterior_inv = inventario_abierto #estado anterior para comparar si se abre o si de cierra

                    #el inventario queda abieto si: (palma_abierta) + mano_horizontal + dorso_hacia_la_camara
                    inventario_abierto = es_horizontal and dorso_hacia_camara

                    if inventario_abierto and not estado_anterior_inv: print("\n[+] INVENTARIO ABIERTO") #abrir inventario si no estaba abierto
                    elif not inventario_abierto and estado_anterior_inv: print("[-] INVENTARIO CERRADO") #cerrar inventario si estaba abierto

                    #-----LOGICA INVENTARIO------

                    if inventario_abierto: 
                        tiempo_inicio_pausa = 0 #para pausar el juego inciamos el contador de pausa
                        pulgar_listo_para_disparar = False #variable que indica posicion del pulgar
                        
                        cv2.putText(frame, "INVENTARIO ACTIVO", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

                        #Para el inventario tenemos en cuenta las puntas de los dedos a excepción del pulgar
                        puntas_dedos = [8, 12, 16, 20]

                        for punta_idx in puntas_dedos: #iteramos para cada punta para comprobar su estado

                            #vemos si la punta del dedo está doblada para seleccionar un item
                            dedo_doblado = calcular_distancia(puntos[punta_idx], muneca) < calcular_distancia(puntos[punta_idx - 2], muneca)
                            if dedo_doblado and not estado_dedos_doblados[punta_idx]: #unicamente un gesto por ciclo, pero dentro del inventario podemos activar varios
                                print(f"   -> Usando gesto: {nombres_objetos[punta_idx]}") #imprimos del diccionario la información
                                with lock:
                                    items_usados_buffer.append(punta_idx) #buffer de items usados simultáneamente
                            estado_dedos_doblados[punta_idx] = dedo_doblado

                    else:
                        for clave in estado_dedos_doblados.keys(): estado_dedos_doblados[clave] = False

                        if es_palma_abierta:
                            pulgar_listo_para_disparar = False
                            if tiempo_inicio_pausa == 0: tiempo_inicio_pausa = time.time()
                            elapsed = time.time() - tiempo_inicio_pausa
                            cv2.putText(frame, f"Pausando... {int((elapsed/2)*100)}%", (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
                            
                            if elapsed >= 2.0:
                                print("\n[-] JUEGO EN PAUSA")
                                with lock: trigger_pause = True
                                tiempo_inicio_pausa = 0
                        else:
                            tiempo_inicio_pausa = 0
                            es_mano_derecha = (etiqueta_mano == "Right")
                            palma_de_frente = puntos[5].x < puntos[17].x 
                            gesto_pistola = indice_ext and not medio_ext and not anular_ext and not menique_ext
                            gesto_metralleta = indice_ext and medio_ext and not anular_ext and not menique_ext

                            if es_mano_derecha and palma_de_frente and (gesto_pistola or gesto_metralleta):

                                if gesto_pistola : #el gesto de metralleta incluye el gesto de pistola
                                    cv2.putText(frame, "PISTOLA LISTA", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 165, 255), 2)
                                    with lock: arma_activa = "Pistola"
                                elif gesto_metralleta :
                                    cv2.putText(frame, "METRALLETA  LISTA", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 165, 255), 2)
                                    with lock: arma_activa = "Metralleta"

                                #Comprabamos si el gatillo está levantado
                                pulgar_extendido = puntos[4].x < puntos[3].x
                                
                                if pulgar_extendido:
                                    pulgar_listo_para_disparar = True
                                    cv2.putText(frame, "Gatillo: Listo", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                                else:
                                    cv2.putText(frame, "Gatillo: Apretado", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                                    tiempo_actual = time.time()

                                    if gesto_pistola : #para la pistola un único trigger por gesto
                                        if pulgar_listo_para_disparar and balas_pistola > 0:
                                            print("[!] PUM! Disparo efectuado")
                                            
                                            with lock: 
                                                trigger_shoot = True
                                                balas_pistola -= 1
                                            pulgar_listo_para_disparar = False

                                    elif gesto_metralleta and balas_metralleta > 0:
                                        #para la metralleta disparamos con cooldown
                                        if tiempo_actual - time_ultimo_disparo > CADENCIA_METRALLETA:
                                            print("[!] RATATATA! Disparo de Metralleta")

                                            with lock: 
                                                trigger_shoot = True #mantenemos a true la flag de trigger y de pulgar
                                                balas_metralleta -= 1
                                            time_ultimo_disparo = tiempo_actual         
                            else:
                                pulgar_listo_para_disparar = False

                            #Puño cerrado para recargar fuera del estado de pausa
                            if es_puno_cerrado:
                                

                                #Solo recarga una vez por gesto -> similar al trigger de la pistola
                                if listo_para_recargar and (tiempo_actual - time_ultima_recarga > TIEMPO_RECARGA):
                                    
                                    with lock: #para imprimir las balas recargadas en el hilo principal de pygame
                                        recharge_weapon = True
                                    if recharge_sound: #sonido solo una vez por recarga
                                        try:
                                            recharge_sound.play()
                                        except Exception:
                                            pass

                                    balas_pistola = MAX_BALAS_PISTOLA #recargamos la pistola (podriamos poner que recargue solo la que se esté usando, pero para simplificar recargamos ambas)
                                    balas_metralleta = MAX_BALAS_METRALLETA #recargamos la metralleta
                                    time_ultima_recarga = tiempo_actual
                                    listo_para_recargar = False  #requiere abrir la mano para volver a activar

                                else : 
                                    if balas_pistola == MAX_BALAS_PISTOLA and balas_metralleta == MAX_BALAS_METRALLETA: #arma ya recargada
                                        cv2.putText(frame, "Arma recargada", (10, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                                

                            else:
                                # Cuando el usuario abre la mano, rearmamos el mecanismo para la próxima recarga
                                listo_para_recargar = True
                                                            

                            

            cv2.imshow("Camara - MediaPipe", frame)
            if cv2.waitKey(1) & 0xFF == 27:
                running = False
                break

    cap.release()
    cv2.destroyAllWindows()


# INICIALIZACIÓN DE BUCLE PRINCIPAL
thread_camera = threading.Thread(target=camara_thread)
thread_camera.daemon = True
thread_camera.start()

# Los enemigos ya no spawnean a menos de 50px de los bordes
targets = [{"x": random.randint(TARGET_RADIUS + 50, WIDTH - TARGET_RADIUS - 50), "y": random.randint(TARGET_RADIUS + 60, HEIGHT - TARGET_RADIUS), "spawn_time": pygame.time.get_ticks()} for _ in range(2)]
effects = []
mensajes_visuales = [] 
drops_flotantes = [] 
pygame.time.set_timer(pygame.USEREVENT + 1, SPAWN_INTERVAL_MS)

barra_jugador = BarraVida((WIDTH/2)-150, HEIGHT-50, 300, 25, 100)
hud_inventario = HUDInventario()
mira = Mira()
puntuacion_total = 0

cantidades_inventario = {8: 0, 12: 0, 16: 0, 20: 0}
kills_para_ulti_actual = 0
nombres_items = {8: "Botiquín", 12: "Munición Explosiva", 16: "Escudo", 20: "HABILIDAD DEFINITIVA"}

# Variables del Escudo
shield_active = False
shield_start_time = 0
SHIELD_DURATION_MS = 5000

# Variables Munición Explosiva
explosive_active = False
explosive_start_time = 0
EXPLOSIVE_DURATION_MS = 5000

pause_background = None
pause_start_time = 0

while running:
    current_time = pygame.time.get_ticks()

    with lock:
        cur_hand_x, cur_hand_y = hand_x, hand_y
        local_trigger_shoot = trigger_shoot
        local_trigger_pause = trigger_pause
        local_trigger_unpause = trigger_unpause
        
        local_balas_pistola = balas_pistola
        local_balas_metralleta = balas_metralleta
        local_arma_activa = arma_activa
        
        items_a_usar = list(items_usados_buffer)
        items_usados_buffer.clear()

        if trigger_shoot: trigger_shoot = False
        if trigger_pause: trigger_pause = False
        if trigger_unpause: trigger_unpause = False

    if local_trigger_shoot and shoot_sound:
        try: shoot_sound.play()
        except: pass

    # LOGICA DE USO DEL INVENTARIO
    for item in items_a_usar:
        if cantidades_inventario[item] > 0:
            cantidades_inventario[item] -= 1
            if item == 8: # Botiquín
                barra_jugador.curar(25)
                mensajes_visuales.append({"text": "+25 Salud (Botiquín)", "time": current_time, "color": (50, 255, 50)})
            elif item == 12: # Munición Explosiva
                explosive_active = True
                explosive_start_time = current_time
                mensajes_visuales.append({"text": "¡Munición Explosiva por 5s!", "time": current_time, "color": (255, 150, 50)})
            elif item == 16: # Escudo
                shield_active = True
                shield_start_time = current_time
                mensajes_visuales.append({"text": "¡Escudo Activado por 5s!", "time": current_time, "color": (50, 200, 255)})
            elif item == 20: # Ulti
                mensajes_visuales.append({"text": "¡HABILIDAD DEFINITIVA DESATADA!", "time": current_time, "color": (255, 215, 0)})
                for diana in targets[:]:
                    effects.append({"x": diana["x"], "y": diana["y"], "start_time": current_time})
                targets.clear()
        else:
            mensajes_visuales.append({"text": "No tienes ese objeto", "time": current_time, "color": (255, 50, 50)})


    # CONTROL DE ESTADOS DE PYGAME Y TIEMPOS ACTIVOS
    if barra_jugador.vida_actual <= 0:
        screen.blit(capturar_y_desenfocar(screen), (0, 0))
        txt = font_menu.render("GAME OVER", True, (255, 50, 50))
        screen.blit(txt, txt.get_rect(center=(WIDTH//2, HEIGHT//2)))
        pygame.display.flip()
        pygame.time.wait(3000)
        running = False
        continue

    # Verificación de tiempos de habilidades
    if shield_active and current_time - shield_start_time >= SHIELD_DURATION_MS:
        shield_active = False
        
    if explosive_active and current_time - explosive_start_time >= EXPLOSIVE_DURATION_MS:
        explosive_active = False

    if local_trigger_pause and not game_paused:
        with lock: game_paused = True
        pause_background = capturar_y_desenfocar(screen)
        pause_start_time = current_time

    if local_trigger_unpause and game_paused:
        with lock: game_paused = False
        time_paused = current_time - pause_start_time
        # Ajustamos temporizadores
        for diana in targets: diana["spawn_time"] += time_paused
        for eff in effects: eff["start_time"] += time_paused
        for msg in mensajes_visuales: msg["time"] += time_paused
        if shield_active: shield_start_time += time_paused 
        if explosive_active: explosive_start_time += time_paused 

    for event in pygame.event.get():
        if event.type == pygame.QUIT: running = False
        elif event.type == pygame.USEREVENT + 1 and not game_paused and len(targets) < MAX_TARGETS:
            # Spawn con margen de 50px
            targets.append({"x": random.randint(TARGET_RADIUS + 50, WIDTH - TARGET_RADIUS - 50), "y": random.randint(TARGET_RADIUS + 60, HEIGHT - TARGET_RADIUS - 150), "spawn_time": current_time})

    # RENDERIZADO PRINCIPAL Y LÓGICA DE HIT MULTIPLE
    if game_paused:
        screen.blit(pause_background, (0, 0))
        if pause_sprite: screen.blit(pause_sprite, pause_sprite.get_rect(center=(WIDTH//2, HEIGHT//2 - 50)))
        else: screen.blit(font_menu.render("PAUSA", True, (255, 255, 255)), font_menu.render("PAUSA", True, (255, 255, 255)).get_rect(center=(WIDTH//2, HEIGHT//2 - 50)))
        txt_inst = font.render("Manten el PUÑO CERRADO 2s de frente para reanudar", True, (200, 200, 200))
        screen.blit(txt_inst, txt_inst.get_rect(center=(WIDTH//2, HEIGHT//2 + 50)))
    
    else:
        # 1. Evaluar tamaño del área de impacto
        radio_impacto = 120 if explosive_active else TARGET_RADIUS
        disparo_consumido = False
        
        # 2. Lógica de Colisión (Enemigos)
        enemigos_golpeados = []
        for diana in targets[:]:
            distancia = math.hypot(cur_hand_x - diana["x"], cur_hand_y - diana["y"])
            if distancia <= radio_impacto and local_trigger_shoot: 
                enemigos_golpeados.append(diana)
                
        # Procesar aciertos a enemigos en bloque (permite acertar a varios de un tiro)
        if enemigos_golpeados:
            disparo_consumido = True
            for diana in enemigos_golpeados:
                puntuacion_total += max(10, int(100 * (1 - math.hypot(cur_hand_x - diana["x"], cur_hand_y - diana["y"]) / radio_impacto)))
                
                # Carga Ulti
                if cantidades_inventario[20] == 0:
                    kills_para_ulti_actual += 1
                    if kills_para_ulti_actual >= KILLS_PARA_ULTI:
                        cantidades_inventario[20] = 1
                        kills_para_ulti_actual = 0
                        mensajes_visuales.append({"text": "+ ULTI LISTA!", "time": current_time, "color": (255, 215, 0)})

                # Spawn de Drops Físicos
                if random.random() < PROBABILIDAD_DROP:
                    drop_elegido = random.choice([8, 12, 16])
                    drops_flotantes.append({"x": diana["x"], "y": diana["y"], "type": drop_elegido})
                
                if diana in targets:
                    targets.remove(diana)
                    
                effects.append({"x": diana["x"], "y": diana["y"], "start_time": current_time})

        # Comprobar si los enemigos expiran (se salta si lo hemos matado justo en este frame)
        for diana in targets[:]:
            if current_time - diana["spawn_time"] >= TARGET_LIFETIME_MS:
                if not shield_active:
                    effects.append({"x": diana["x"], "y": diana["y"], "start_time": current_time})
                    if expire_sound: 
                        try: expire_sound.play()
                        except: pass
                    barra_jugador.recibir_dano(PENALTY_DAMAGE)
                
                targets.remove(diana)

        # 3. Lógica de Colisión (Drops Flotantes)
        drops_recogidos = []
        for drop in drops_flotantes[:]:
            drop["y"] -= 2.5 
            if drop["y"] < -50:
                drops_flotantes.remove(drop)
                continue
            
            distancia_drop = math.hypot(cur_hand_x - drop["x"], cur_hand_y - drop["y"])
            if distancia_drop <= radio_impacto and local_trigger_shoot:
                drops_recogidos.append(drop)
                
        # Procesar drops recogidos en bloque
        if drops_recogidos:
            disparo_consumido = True
            for drop in drops_recogidos:
                cantidades_inventario[drop["type"]] += 1
                mensajes_visuales.append({"text": f"+ {nombres_items[drop['type']]} Recogido", "time": current_time, "color": (255, 255, 255)})
                if drop in drops_flotantes:
                    drops_flotantes.remove(drop)

        # Consumir el disparo (un solo tiro vale para todo lo que esté en el área)
        if disparo_consumido:
            local_trigger_shoot = False

        # DIBUJADO EN PANTALLA
        screen.blit(background, (0, 0))
        
        # Filtro Azul del Escudo
        if shield_active:
            shield_overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            shield_overlay.fill((0, 150, 255, 60)) 
            screen.blit(shield_overlay, (0, 0))
            
        # Textos superiores de habilidades (Escudo y Explosiva)
        y_text = 70
        if shield_active:
            t_restante = SHIELD_DURATION_MS - (current_time - shield_start_time)
            txt_shield = font_menu.render(f"ESCUDO: {math.ceil(t_restante / 1000)}s", True, (150, 220, 255))
            screen.blit(txt_shield, txt_shield.get_rect(center=(WIDTH // 2, y_text)))
            y_text += 60
            
        if explosive_active:
            t_restante_exp = EXPLOSIVE_DURATION_MS - (current_time - explosive_start_time)
            txt_exp = font_menu.render(f"EXPLOSIVA: {math.ceil(t_restante_exp / 1000)}s", True, (255, 150, 50))
            screen.blit(txt_exp, txt_exp.get_rect(center=(WIDTH // 2, y_text)))

        # Dibujar Enemigos y Drops
        for diana in targets:
            if target_sprite: screen.blit(target_sprite, target_sprite.get_rect(center=(diana["x"], diana["y"])))
            else: pygame.draw.circle(screen, (200, 40, 40), (diana["x"], diana["y"]), TARGET_RADIUS)

        for drop in drops_flotantes:
            img = imagenes_inventario.get(drop["type"])
            if img: screen.blit(img, img.get_rect(center=(drop["x"], drop["y"])))
            else: pygame.draw.circle(screen, (0, 255, 0), (drop["x"], drop["y"]), 25) 

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

        # Mensajes Flotantes 
        for i, msg in enumerate(mensajes_visuales[:]):
            elapsed = current_time - msg["time"]
            if elapsed > 2000:
                mensajes_visuales.remove(msg)
                continue
            alpha = max(0, 255 - int((elapsed / 2000) * 255))
            txt_surf = font.render(msg["text"], True, msg["color"])
            txt_surf.set_alpha(alpha)
            y_offset = (HEIGHT // 2) - (i * 30) - int((elapsed / 2000) * 30)
            screen.blit(txt_surf, txt_surf.get_rect(center=(WIDTH//2, y_offset)))

        # Puntuación y HUD Original
        screen.blit(font.render(f"Puntuación: {puntuacion_total}", True, (255, 255, 255)), (20, 20))
        
        # DIBUJADO DE UI DE ARMAS
        if local_arma_activa == "Pistola":
            txt_arma = font_small.render("Arma activa: Pistola", True, (200, 220, 255))
            # Si se queda sin balas, se pone rojo para alertar visualmente
            color_balas = (255, 255, 0) if local_balas_pistola > 0 else (255, 50, 50)
            txt_municion = font.render(f"{local_balas_pistola}/{MAX_BALAS_PISTOLA}", True, color_balas)
        else:
            txt_arma = font_small.render("Arma activa: Metralleta", True, (200, 220, 255))
            color_balas = (255, 255, 0) if local_balas_metralleta > 0 else (255, 50, 50)
            txt_municion = font.render(f"{local_balas_metralleta}/{MAX_BALAS_METRALLETA}", True, color_balas)

        screen.blit(txt_arma, (20, 55))
        screen.blit(txt_municion, (20, 75))

        hud_inventario.dibujar(screen, cantidades_inventario, kills_para_ulti_actual)
        barra_jugador.dibujar(screen)

    # La mira siempre por encima de todo
    mira.explosiva = explosive_active
    mira.disparando = local_trigger_shoot
    mira.dibujar(screen, (cur_hand_x, cur_hand_y) if cur_hand_x != 0 else None)

    pygame.display.flip()
    clock.tick(60)

running = False
thread_camera.join(timeout=1)
pygame.quit()
cv2.destroyAllWindows()