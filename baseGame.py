import pygame
import random
import math

pygame.init()

# =========================
# CONFIGURACIÓN
# =========================

WIDTH = 1000
HEIGHT = 700

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Dianas")

clock = pygame.time.Clock()

# Imagen de fondo
BACKGROUND_IMAGE = "fondo.png"

background = pygame.image.load(BACKGROUND_IMAGE).convert()
background = pygame.transform.scale(background, (WIDTH, HEIGHT))

# Fuente
font = pygame.font.Font(None, 36)

# =========================
# DIANAS
# =========================

TARGET_RADIUS = 40

targets = []


def crear_diana():
     return {
         "x": random.randint(TARGET_RADIUS, WIDTH - TARGET_RADIUS),
         "y": random.randint(
             TARGET_RADIUS + 60,
             HEIGHT - TARGET_RADIUS
         )
     }


# Número inicial de dianas
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


# =========================
# PUNTUACIÓN SEGÚN PUNTERÍA
# =========================

def calcular_puntuacion(x, y, diana):
     distancia = math.hypot(
         x - diana["x"],
         y - diana["y"]
     )

     if distancia > TARGET_RADIUS:
         return 0

     # Centro = 100 puntos
     # Borde = 10 puntos
     puntuacion = int(
         100 * (1 - distancia / TARGET_RADIUS)
     )

     return max(10, puntuacion)


# =========================
# BUCLE PRINCIPAL
# =========================

puntuacion_total = 0

running = True

while running:

     # -------------------------
     # EVENTOS
     # -------------------------

     for event in pygame.event.get():

         if event.type == pygame.QUIT:
             running = False

         elif event.type == pygame.MOUSEBUTTONDOWN:

             if event.button == 1:

                 mouse_x, mouse_y = pygame.mouse.get_pos()

                 # Comprobar todas las dianas
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

     # -------------------------
     # FONDO
     # -------------------------

     screen.blit(background, (0, 0))

     # -------------------------
     # DIANAS
     # -------------------------

     for diana in targets:
         dibujar_diana(
             diana["x"],
             diana["y"]
         )

     # -------------------------
     # PUNTUACIÓN
     # -------------------------

     texto = font.render(
         f"Puntuación: {puntuacion_total}",
         True,
         (255, 255, 255)
     )

     screen.blit(
         texto,
         (20, 20)
     )

     # -------------------------
     # COORDENADAS DEL APUNTADO
     # -------------------------

     mouse_x, mouse_y = pygame.mouse.get_pos()

     coordenadas = font.render(
         f"Apuntando: ({mouse_x}, {mouse_y})",
         True,
         (255, 255, 255)
     )

     screen.blit(
         coordenadas,
         (20, 55)
     )

     pygame.display.flip()

     clock.tick(60)


pygame.quit()
