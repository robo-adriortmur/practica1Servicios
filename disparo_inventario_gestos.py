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

# Estados del inventario
inventario_abierto = False
estado_dedos_doblados = {8: False, 12: False, 16: False, 20: False}

# Estado del disparo
pulgar_listo_para_disparar = False

def calcular_distancia(punto1, punto2):
    return math.hypot(punto1.x - punto2.x, punto1.y - punto2.y)

cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)

with mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=1,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
) as hands:

    while cap.isOpened():
        exito, frame = cap.read()
        if not exito:
            break

        frame = cv2.flip(frame, 1)
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        resultados = hands.process(frame_rgb)

        if resultados.multi_hand_landmarks and resultados.multi_handedness:
            mano = resultados.multi_hand_landmarks[0]
            # Obtener si es la mano derecha (después del efecto espejo)
            etiqueta_mano = resultados.multi_handedness[0].classification[0].label
            
            mp_drawing.draw_landmarks(frame, mano, mp_hands.HAND_CONNECTIONS)
            
            puntos = mano.landmark
            muneca = puntos[0]
            
            # ==========================================
            # LÓGICA DEL INVENTARIO (Mano Horizontal)
            # ==========================================
            mcp_medio = puntos[9]
            dist_x = abs(mcp_medio.x - muneca.x)
            dist_y = abs(mcp_medio.y - muneca.y)
            es_horizontal = dist_x > 1.2 * dist_y

            mcp_pulgar = puntos[2]
            mcp_menique = puntos[17]
            dorso_hacia_camara = mcp_pulgar.y < mcp_menique.y

            estado_anterior_inventario = inventario_abierto
            inventario_abierto = es_horizontal and dorso_hacia_camara

            if inventario_abierto and not estado_anterior_inventario:
                print("\n[+] INVENTARIO ABIERTO")
            elif not inventario_abierto and estado_anterior_inventario:
                print("[-] INVENTARIO CERRADO")

            # ==========================================
            # EJECUCIÓN DE ACCIONES
            # ==========================================
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
                # Reseteamos los dedos del inventario al cerrarlo
                for clave in estado_dedos_doblados.keys():
                    estado_dedos_doblados[clave] = False

                # ==========================================
                # LÓGICA DE DISPARO (Pistola)
                # ==========================================
                # 1. Verificar que sea la mano derecha de frente (índice a la izquierda del meñique)
                es_mano_derecha = (etiqueta_mano == "Right")
                palma_de_frente = puntos[5].x < puntos[17].x 
                
                # 2. Verificar si los dedos están en posición (Índice estirado, los demás cerrados)
                indice_extendido = calcular_distancia(puntos[8], muneca) > calcular_distancia(puntos[6], muneca)
                medio_cerrado = calcular_distancia(puntos[12], muneca) < calcular_distancia(puntos[10], muneca)
                anular_cerrado = calcular_distancia(puntos[16], muneca) < calcular_distancia(puntos[14], muneca)
                menique_cerrado = calcular_distancia(puntos[20], muneca) < calcular_distancia(puntos[18], muneca)

                gesto_pistola = indice_extendido and medio_cerrado and anular_cerrado and menique_cerrado

                if es_mano_derecha and palma_de_frente and gesto_pistola:
                    cv2.putText(frame, "ARMA LISTA", (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 165, 255), 2)
                    
                    # 3. Lógica del gatillo (Pulgar)
                    # En la mano derecha de frente, si el pulgar está estirado, su punta (4) está más a la izquierda (menor X) que su nudillo (3)
                    pulgar_extendido = puntos[4].x < puntos[3].x
                    
                    if pulgar_extendido:
                        pulgar_listo_para_disparar = True
                        cv2.putText(frame, "Gatillo: Listo", (30, 85), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                    else:
                        # Si el pulgar se cierra y estaba listo para disparar, efectuamos el disparo
                        if pulgar_listo_para_disparar:
                            print("\n[!] PUM! Disparo efectuado")
                            pulgar_listo_para_disparar = False
                        cv2.putText(frame, "Gatillo: Apretado", (30, 85), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                else:
                    # Si perdemos la forma de la pistola, reseteamos el seguro
                    pulgar_listo_para_disparar = False

        cv2.imshow("Prueba de Inventario y Disparo", frame)

        if cv2.waitKey(1) & 0xFF == 27:
            break

cap.release()
cv2.destroyAllWindows()