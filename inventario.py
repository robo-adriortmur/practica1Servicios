import cv2
import mediapipe as mp
import math

mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils

nombres_objetos = {
    8: "Objeto 1 (Dedo Índice)", 
    12: "Objeto 2 (Dedo Medio)", 
    16: "Objeto 3 (Dedo Anular)", 
    20: "Objeto 4 (Dedo Meñique)"
}

inventario_abierto = False
estado_dedos_doblados = {8: False, 12: False, 16: False, 20: False}

def calcular_distancia(punto1, punto2):
    return math.hypot(punto1.x - punto2.x, punto1.y - punto2.y)

# Añadido CAP_DSHOW igual que en tu baseGame.py para evitar problemas en Windows
cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)

with mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=1,
    min_detection_confidence=0.5, # Reducido a 0.5 para que detecte la mano más fácilmente
    min_tracking_confidence=0.5
) as hands:

    while cap.isOpened():
        exito, frame = cap.read()
        if not exito:
            break

        frame = cv2.flip(frame, 1)
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        resultados = hands.process(frame_rgb)

        if resultados.multi_hand_landmarks:
            mano = resultados.multi_hand_landmarks[0]
            mp_drawing.draw_landmarks(frame, mano, mp_hands.HAND_CONNECTIONS)
            
            puntos = mano.landmark
            muneca = puntos[0]
            
            # 1. ¿Está horizontal? Rebajamos la exigencia matemática a 1.2
            mcp_medio = puntos[9]
            dist_x = abs(mcp_medio.x - muneca.x)
            dist_y = abs(mcp_medio.y - muneca.y)
            es_horizontal = dist_x > 1.2 * dist_y

            # 2. ¿Dorso hacia la cámara? 
            # Corrección: El pulgar queda ARRIBA (Y menor) cuando el dorso mira a la cámara
            mcp_pulgar = puntos[2]
            mcp_menique = puntos[17]
            dorso_hacia_camara = mcp_pulgar.y < mcp_menique.y

            estado_anterior_inventario = inventario_abierto
            inventario_abierto = es_horizontal and dorso_hacia_camara

            if inventario_abierto and not estado_anterior_inventario:
                print("\n[+] INVENTARIO ABIERTO")
            elif not inventario_abierto and estado_anterior_inventario:
                print("[-] INVENTARIO CERRADO")

            if inventario_abierto:
                cv2.putText(frame, "INVENTARIO ACTIVO", (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                puntas_dedos = [8, 12, 16, 20]
                
                for punta_idx in puntas_dedos:
                    pip_idx = punta_idx - 2 
                    dist_punta_muneca = calcular_distancia(puntos[punta_idx], muneca)
                    dist_pip_muneca = calcular_distancia(puntos[pip_idx], muneca)
                    
                    dedo_doblado = dist_punta_muneca < dist_pip_muneca
                    
                    if dedo_doblado and not estado_dedos_doblados[punta_idx]:
                        print(f"   -> Usando: {nombres_objetos[punta_idx]}")
                        
                    estado_dedos_doblados[punta_idx] = dedo_doblado
            else:
                for clave in estado_dedos_doblados.keys():
                    estado_dedos_doblados[clave] = False

            # DEBUG VISUAL: Te mostrará en pantalla qué condición se está cumpliendo
            color_horiz = (0, 255, 0) if es_horizontal else (0, 0, 255)
            color_dorso = (0, 255, 0) if dorso_hacia_camara else (0, 0, 255)
            cv2.putText(frame, f"Horizontal: {es_horizontal}", (10, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color_horiz, 2)
            cv2.putText(frame, f"Dorso de frente: {dorso_hacia_camara}", (10, 130), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color_dorso, 2)

        cv2.imshow("Prueba de Inventario", frame)

        if cv2.waitKey(1) & 0xFF == 27:
            break

cap.release()
cv2.destroyAllWindows()