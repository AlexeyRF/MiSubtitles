import pygame
import pygame_gui
import sys
import math
import random
from pygame.locals import *

try:
    import imageio
    import numpy as np
    from PIL import Image
    EXPORT_AVAILABLE = True
except ImportError:
    EXPORT_AVAILABLE = False
    print("Для экспорта установите: pip install imageio pillow imageio[ffmpeg]")

SCREEN_WIDTH = 1000
SCREEN_HEIGHT = 700
BACKGROUND_COLOR = (20, 20, 30)
TRANSPARENT_BG = (0, 0, 0, 0)
FONT_SIZE = 80

BASE_GRAVITY = 500.0
BASE_VX_RANGE = (-180, 180)      
BASE_VY_RANGE = (-280, -80)      

BASE_RX_SPEED_RANGE = (-2.5, 2.5)
BASE_RY_SPEED_RANGE = (-2.5, 2.5)
BASE_RZ_SPEED_RANGE = (-150, 150)   

def create_sparks(x, y, count, life, min_speed, max_speed, color=(255, 255, 255)):
    new_sparks = []
    actual_min_speed = min(min_speed, max_speed)
    actual_max_speed = max(min_speed, max_speed)
    
    for _ in range(int(count)):
        angle = random.uniform(math.pi + 0.2, 2 * math.pi - 0.2)
        speed = random.uniform(actual_min_speed, actual_max_speed)
        vx = math.cos(angle) * speed
        vy = math.sin(angle) * speed
        lifetime = life * random.uniform(0.5, 1.5)
        new_sparks.append(Spark(x, y, vx, vy, lifetime, color))
    return new_sparks

class Spark:
    def __init__(self, x, y, vx, vy, lifetime, color):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.lifetime = lifetime
        self.age = 0.0
        self.gravity = 600.0 
        self.color = color

    def update(self, dt):
        self.vy += self.gravity * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.age += dt

    def is_alive(self):
        return self.age < self.lifetime

    def draw(self, screen):
        alpha = 1.0 - (self.age / self.lifetime)
        if alpha <= 0:
            return

        r, g, b = self.color[0], self.color[1], self.color[2]
        color_with_alpha = (r, g, b, int(255 * alpha))

        tail_length = 0.06
        end_x = self.x - self.vx * tail_length
        end_y = self.y - self.vy * tail_length
        
        thickness = max(1, int(6 * alpha))
        pygame.draw.line(screen, color_with_alpha, (int(self.x), int(self.y)), (int(end_x), int(end_y)), thickness)

class FallingLetter:
    def __init__(self, surface, center_x, center_y, shrink_duration, motion_factor, rot_factor, start_time):
        self.active = True
        self.original_surf = surface 

        self.x = float(center_x)
        self.y = float(center_y)

        self.base_vx = random.uniform(*BASE_VX_RANGE)
        self.base_vy = random.uniform(*BASE_VY_RANGE)
        self.base_gravity = BASE_GRAVITY

        self.rx = 0.0
        self.ry = 0.0
        self.rz = 0.0

        self.base_rx_speed = random.uniform(*BASE_RX_SPEED_RANGE)
        self.base_ry_speed = random.uniform(*BASE_RY_SPEED_RANGE)
        self.base_rz_speed = random.uniform(*BASE_RZ_SPEED_RANGE)

        self.start_time = start_time
        self.shrink_duration = shrink_duration
        self.motion_factor = motion_factor
        self.rot_factor = rot_factor
        self.shrink_scale = 1.0

    def update(self, current_time, dt, motion_factor, rot_factor):
        if not self.active:
            return

        elapsed = current_time - self.start_time
        progress = min(1.0, elapsed / self.shrink_duration)
        self.shrink_scale = 1.0 - progress
        if progress >= 1.0:
            self.active = False
            return

        eff_vx = self.base_vx * motion_factor
        eff_vy = self.base_vy * motion_factor
        eff_gravity = self.base_gravity * motion_factor

        self.x += eff_vx * dt
        self.y += eff_vy * dt
        self.base_vy += eff_gravity * dt

        self.rx += self.base_rx_speed * dt * rot_factor
        self.ry += self.base_ry_speed * dt * rot_factor
        self.rz += self.base_rz_speed * dt * rot_factor

    def draw(self, screen):
        if not self.active:
            return

        sx = max(0.1, abs(math.cos(self.ry)))
        sy = max(0.1, abs(math.cos(self.rx)))
        sx *= self.shrink_scale
        sy *= self.shrink_scale

        orig_w, orig_h = self.original_surf.get_size()
        new_w = max(1, int(orig_w * sx))
        new_h = max(1, int(orig_h * sy))

        scaled = pygame.transform.scale(self.original_surf, (new_w, new_h))
        rotated = pygame.transform.rotate(scaled, self.rz)

        rect = rotated.get_rect(center=(int(self.x), int(self.y)))
        screen.blit(rotated, rect)

class SentenceManager:
    def __init__(self, text, color, disintegrate_time, shrink_dur, motion_factor, rot_factor, spark_params, start_time=0.0):
        self.letters_data = []
        self.sparks = []
        pygame.font.init()
        self.font = pygame.font.SysFont('arial', FONT_SIZE) 
        self.color = color
        self.spark_params = spark_params
        
        out_w = 2
        char_widths = [self.font.size(char)[0] + out_w * 2 for char in text]
        total_width = sum(char_widths)
        start_x = SCREEN_WIDTH / 2 - total_width / 2
        start_y = SCREEN_HEIGHT / 2

        current_x = start_x
        current_time = start_time

        for i, char in enumerate(text):
            if char != " ":
                color_white = (255, 255, 255)
                outline_color = (255, 255, 255)
                
                base_normal = self.font.render(char, True, self.color)
                base_white = self.font.render(char, True, color_white)
                w, h = base_normal.get_size()
                
                surf_n = pygame.Surface((w + out_w * 2, h + out_w * 2), pygame.SRCALPHA)
                surf_w = pygame.Surface((w + out_w * 2, h + out_w * 2), pygame.SRCALPHA)
                
                for dx in [-out_w, 0, out_w]:
                    for dy in [-out_w, 0, out_w]:
                        if dx == 0 and dy == 0:
                            continue
                        outline = self.font.render(char, True, outline_color)
                        surf_n.blit(outline, (dx + out_w, dy + out_w))
                        surf_w.blit(outline, (dx + out_w, dy + out_w))
                        
                surf_n.blit(base_normal, (out_w, out_w))
                surf_w.blit(base_white, (out_w, out_w))

                appear_delay = i * 0.04
                appearance_time = appear_delay + 0.8 
                disint_delay = 0 if len(text) <= 1 else (i / (len(text) - 1)) * disintegrate_time
                
                center_x = current_x + char_widths[i] / 2
                
                self.letters_data.append({
                    'char': char,
                    'surf_n': surf_n,
                    'surf_w': surf_w,
                    'target_x': center_x,
                    'current_x': center_x + 15, 
                    'center_y': start_y,
                    'activation_time': current_time + appearance_time + disint_delay,
                    'obj': None,
                    'shrink_dur': shrink_dur,
                    'appear_delay': appear_delay,
                    'color_progress': 0.0
                })
            current_x += char_widths[i]

    def update(self, current_time, dt, motion_factor, rot_factor):
        move_speed = 12.0 

        for item in self.letters_data:
            if item['obj'] is None:
                if item['appear_delay'] > 0:
                    item['appear_delay'] -= dt
                else:
                    item['current_x'] += (item['target_x'] - item['current_x']) * move_speed * dt
                    if item['color_progress'] < 1.0:
                        item['color_progress'] += 3.0 * dt
                        if item['color_progress'] > 1.0:
                            item['color_progress'] = 1.0

                if current_time >= item['activation_time']:
                    item['obj'] = FallingLetter(
                        item['surf_n'], item['current_x'], item['center_y'], 
                        item['shrink_dur'], motion_factor, rot_factor, current_time
                    )
                    self.sparks.extend(create_sparks(item['current_x'], item['center_y'], *self.spark_params, self.color))

        for item in self.letters_data:
            if item['obj'] is not None:
                item['obj'].update(current_time, dt, motion_factor, rot_factor)

        for spark in self.sparks[:]:
            spark.update(dt)
            if not spark.is_alive():
                self.sparks.remove(spark)

    def draw(self, screen):
        for spark in self.sparks:
            spark.draw(screen)

        for item in self.letters_data:
            if item['obj'] is not None and item['obj'].active:
                item['obj'].draw(screen)
            elif item['obj'] is None:
                if item['appear_delay'] > 0:
                    continue
                
                w, h = item['surf_w'].get_size()
                pos_x = int(item['current_x']) - w // 2
                pos_y = int(item['center_y']) - h // 2
               
                screen.blit(item['surf_w'], (pos_x, pos_y))
                
                if item['color_progress'] > 0.0:
                    clip_w = int(w * item['color_progress'])
                    if clip_w > 0:
                        clip_rect = pygame.Rect(0, 0, clip_w, h)
                        screen.blit(item['surf_n'], (pos_x, pos_y), area=clip_rect)

    def is_complete(self):
        for item in self.letters_data:
            if item['obj'] is not None and item['obj'].active:
                return False
            if item['obj'] is None:
                return False
        return len(self.sparks) == 0

class AnimationExporter:
    def __init__(self, screen_width, screen_height, fps=30):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.fps = fps
        self.frames = []
        
    def capture_frame(self, screen, transparent=False):
        if transparent:
            frame_surface = pygame.Surface((self.screen_width, self.screen_height), pygame.SRCALPHA)
            frame_surface.blit(screen, (0, 0))
            
            frame_data = pygame.surfarray.array3d(frame_surface)
            alpha = pygame.surfarray.array_alpha(frame_surface)
            
            frame_data = np.transpose(frame_data, (1, 0, 2))
            alpha = np.transpose(alpha, (1, 0))
            
            frame_data = np.dstack((frame_data, alpha))
        else:
            frame_data = pygame.surfarray.array3d(screen)
            
            frame_data = np.transpose(frame_data, (1, 0, 2))
        
        self.frames.append(frame_data)
        
    def save_as_gif(self, filename, duration=0.033):
        if not EXPORT_AVAILABLE:
            return False
        try:
            gif_frames = []
            for frame in self.frames:
                if frame.shape[2] == 4:
                    rgb_frame = np.zeros((frame.shape[0], frame.shape[1], 3), dtype=np.uint8)
                    alpha = frame[:, :, 3] / 255.0
                    for c in range(3):
                        rgb_frame[:, :, c] = (frame[:, :, c] * alpha).astype(np.uint8)
                    gif_frames.append(rgb_frame)
                else:
                    gif_frames.append(frame)
            imageio.mimsave(filename, gif_frames, format='GIF', duration=duration, loop=0)
            return True
        except Exception as e:
            print(f"Ошибка сохранения GIF: {e}")
            return False
    
    def save_as_mp4(self, filename):
        if not EXPORT_AVAILABLE:
            return False
        try:
            writer = imageio.get_writer(filename, fps=self.fps, format='FFMPEG', codec='libx264', 
                                       output_params=['-pix_fmt', 'yuva420p'] if self.frames[0].shape[2] == 4 else [])
            for frame in self.frames:
                writer.append_data(frame)
            writer.close()
            return True
        except Exception as e:
            print(f"Ошибка сохранения MP4: {e}")
            return False
    
    def clear(self):
        self.frames = []

def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    pygame.display.set_caption("Анимация Текста")
    clock = pygame.time.Clock()
    manager = pygame_gui.UIManager((SCREEN_WIDTH, SCREEN_HEIGHT))

    current_text_color = pygame.Color(255, 220, 100)
    transparent_bg = False
    exporter = AnimationExporter(SCREEN_WIDTH, SCREEN_HEIGHT, 30)

    text_label = pygame_gui.elements.UILabel(
        relative_rect=pygame.Rect((20, 20), (80, 30)), text="Текст:", manager=manager
    )
    text_entry = pygame_gui.elements.UITextEntryLine(
        relative_rect=pygame.Rect((100, 20), (270, 30)), manager=manager
    )
    text_entry.set_text("Привет Мир")

    color_button = pygame_gui.elements.UIButton(
        relative_rect=pygame.Rect((20, 70), (150, 30)), text="Выбрать цвет", manager=manager
    )
    color_preview_rect = pygame.Rect((180, 70), (30, 30))

    motion_speed_slider = pygame_gui.elements.UIHorizontalSlider(
        relative_rect=pygame.Rect((20, 120), (200, 30)), start_value=1.0, value_range=(0.3, 3.0), manager=manager
    )
    motion_label = pygame_gui.elements.UILabel(
        relative_rect=pygame.Rect((230, 120), (180, 30)), text="Скор. движ.: 1.00", manager=manager
    )

    rotation_speed_slider = pygame_gui.elements.UIHorizontalSlider(
        relative_rect=pygame.Rect((20, 170), (200, 30)), start_value=1.0, value_range=(0.2, 3.0), manager=manager
    )
    rotation_label = pygame_gui.elements.UILabel(
        relative_rect=pygame.Rect((230, 170), (180, 30)), text="Скор. вращ.: 1.00", manager=manager
    )

    shrink_duration_slider = pygame_gui.elements.UIHorizontalSlider(
        relative_rect=pygame.Rect((20, 220), (200, 30)), start_value=2.0, value_range=(0.5, 5.0), manager=manager
    )
    shrink_label = pygame_gui.elements.UILabel(
        relative_rect=pygame.Rect((230, 220), (180, 30)), text="Уменьшение: 2.00 с", manager=manager
    )

    disintegration_slider = pygame_gui.elements.UIHorizontalSlider(
        relative_rect=pygame.Rect((20, 270), (200, 30)), start_value=1.5, value_range=(0.0, 5.0), manager=manager
    )
    disintegration_label = pygame_gui.elements.UILabel(
        relative_rect=pygame.Rect((230, 270), (180, 30)), text="Распад: 1.50 с", manager=manager
    )

    COL2_X = 450

    spark_count_slider = pygame_gui.elements.UIHorizontalSlider(
        relative_rect=pygame.Rect((COL2_X, 20), (200, 30)), start_value=60, value_range=(10, 150), manager=manager
    )
    spark_count_label = pygame_gui.elements.UILabel(
        relative_rect=pygame.Rect((COL2_X + 210, 20), (160, 30)), text="Искр: 60", manager=manager
    )

    spark_life_slider = pygame_gui.elements.UIHorizontalSlider(
        relative_rect=pygame.Rect((COL2_X, 70), (200, 30)), start_value=0.7, value_range=(0.2, 2.0), manager=manager
    )
    spark_life_label = pygame_gui.elements.UILabel(
        relative_rect=pygame.Rect((COL2_X + 210, 70), (160, 30)), text="Жизнь искр: 0.70 с", manager=manager
    )

    spark_min_speed_slider = pygame_gui.elements.UIHorizontalSlider(
        relative_rect=pygame.Rect((COL2_X, 120), (200, 30)), start_value=100, value_range=(10, 300), manager=manager
    )
    spark_min_speed_label = pygame_gui.elements.UILabel(
        relative_rect=pygame.Rect((COL2_X + 210, 120), (160, 30)), text="Мин. скор.: 100", manager=manager
    )

    spark_max_speed_slider = pygame_gui.elements.UIHorizontalSlider(
        relative_rect=pygame.Rect((COL2_X, 170), (200, 30)), start_value=350, value_range=(100, 600), manager=manager
    )
    spark_max_speed_label = pygame_gui.elements.UILabel(
        relative_rect=pygame.Rect((COL2_X + 210, 170), (160, 30)), text="Макс. скор.: 350", manager=manager
    )

    COL3_X = 770
    
    transparent_checkbox = pygame_gui.elements.UIButton(
        relative_rect=pygame.Rect((COL3_X, 20), (210, 30)), 
        text="Прозрачный фон: ВЫКЛ", manager=manager
    )
    
    start_button = pygame_gui.elements.UIButton(
        relative_rect=pygame.Rect((COL2_X, 240), (250, 60)), text="ТЕСТ АНИМАЦИИ", manager=manager
    )
    
    export_gif_button = pygame_gui.elements.UIButton(
        relative_rect=pygame.Rect((COL3_X, 70), (210, 40)), text="Быстрый экспорт GIF", manager=manager
    )
    
    export_mp4_button = pygame_gui.elements.UIButton(
        relative_rect=pygame.Rect((COL3_X, 120), (210, 40)), text="Быстрый экспорт MP4", manager=manager
    )
   
    status_label = pygame_gui.elements.UILabel(
        relative_rect=pygame.Rect((COL3_X, 180), (210, 60)), 
        text="Готов", manager=manager
    )

    sentence_manager = None
    color_picker = None
    animation_complete = False

    def render_and_export(filename, format_type):
        status_label.set_text("Рендеринг... Подождите.")
        pygame.display.flip() 

        exporter.clear()
        
        text = text_entry.get_text().strip() or "Привет"
        motion_factor = motion_speed_slider.get_current_value()
        rot_factor = rotation_speed_slider.get_current_value()
        shrink_dur = shrink_duration_slider.get_current_value()
        disintegrate_time = disintegration_slider.get_current_value()
        
        spark_params = (
            spark_count_slider.get_current_value(),
            spark_life_slider.get_current_value(),
            spark_min_speed_slider.get_current_value(),
            spark_max_speed_slider.get_current_value()
        )
        
        sim_time = 0.0
        dt = 1.0 / exporter.fps
        
        render_manager = SentenceManager(
            text, current_text_color, disintegrate_time, shrink_dur, 
            motion_factor, rot_factor, spark_params, start_time=sim_time
        )
        
        render_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        max_frames = exporter.fps * 15
        frames_rendered = 0
        
        while not render_manager.is_complete() and frames_rendered < max_frames:
            if transparent_bg:
                render_surface.fill((0, 0, 0, 0))
            else:
                render_surface.fill(BACKGROUND_COLOR)
                
            render_manager.update(sim_time, dt, motion_factor, rot_factor)
            render_manager.draw(render_surface)
            
            exporter.capture_frame(render_surface, transparent=transparent_bg)
            
            sim_time += dt
            frames_rendered += 1

        status_label.set_text("Сохранение файла...")
        pygame.display.flip()

        if format_type == 'gif':
            success = exporter.save_as_gif(filename)
        else:
            success = exporter.save_as_mp4(filename)
            
        if success:
            status_label.set_text(f"Успешно сохранено!")
        else:
            status_label.set_text("Ошибка экспорта!")

    running = True
    while running:
        time_delta = clock.tick(60) / 1000.0
        current_time = pygame.time.get_ticks() / 1000.0

        for event in pygame.event.get():
            if event.type == QUIT:
                running = False
            
            if event.type == pygame_gui.UI_BUTTON_PRESSED:
                if event.ui_element == start_button:
                    text = text_entry.get_text().strip() or "Привет"
                    spark_params = (
                        spark_count_slider.get_current_value(),
                        spark_life_slider.get_current_value(),
                        spark_min_speed_slider.get_current_value(),
                        spark_max_speed_slider.get_current_value()
                    )
                    sentence_manager = SentenceManager(
                        text, current_text_color, 
                        disintegration_slider.get_current_value(), 
                        shrink_duration_slider.get_current_value(), 
                        motion_speed_slider.get_current_value(), 
                        rotation_speed_slider.get_current_value(), 
                        spark_params, start_time=current_time
                    )
                    animation_complete = False
                    status_label.set_text("Предпросмотр...")

                elif event.ui_element == color_button:
                    color_picker = pygame_gui.windows.UIColourPickerDialog(
                        rect=pygame.Rect(160, 50, 420, 400),
                        manager=manager,
                        window_title="Выберите цвет текста",
                        initial_colour=current_text_color
                    )
                elif event.ui_element == transparent_checkbox:
                    transparent_bg = not transparent_bg
                    if transparent_bg:
                        transparent_checkbox.set_text("Прозрачный фон: ВКЛ")
                    else:
                        transparent_checkbox.set_text("Прозрачный фон: ВЫКЛ")

                elif event.ui_element == export_gif_button:
                    from tkinter import filedialog, Tk
                    root = Tk()
                    root.withdraw()
                    filename = filedialog.asksaveasfilename(
                        defaultextension=".gif",
                        filetypes=[("GIF файлы", "*.gif")]
                    )
                    root.destroy()
                    if filename:
                        render_and_export(filename, 'gif')

                elif event.ui_element == export_mp4_button:
                    from tkinter import filedialog, Tk
                    root = Tk()
                    root.withdraw()
                    filename = filedialog.asksaveasfilename(
                        defaultextension=".mp4",
                        filetypes=[("MP4 файлы", "*.mp4")]
                    )
                    root.destroy()
                    if filename:
                        render_and_export(filename, 'mp4')

            if event.type == pygame_gui.UI_COLOUR_PICKER_COLOUR_PICKED:
                current_text_color = event.colour
            
            if event.type == pygame_gui.UI_HORIZONTAL_SLIDER_MOVED:
                if event.ui_element == motion_speed_slider:
                    motion_label.set_text(f"Скор. движ.: {event.value:.2f}")
                elif event.ui_element == rotation_speed_slider:
                    rotation_label.set_text(f"Скор. вращ.: {event.value:.2f}")
                elif event.ui_element == shrink_duration_slider:
                    shrink_label.set_text(f"Уменьшение: {event.value:.2f} с")
                elif event.ui_element == disintegration_slider:
                    disintegration_label.set_text(f"Распад: {event.value:.2f} с")
                elif event.ui_element == spark_count_slider:
                    spark_count_label.set_text(f"Искр: {int(event.value)}")
                elif event.ui_element == spark_life_slider:
                    spark_life_label.set_text(f"Жизнь искр: {event.value:.2f} с")
                elif event.ui_element == spark_min_speed_slider:
                    spark_min_speed_label.set_text(f"Мин. скор.: {int(event.value)}")
                elif event.ui_element == spark_max_speed_slider:
                    spark_max_speed_label.set_text(f"Макс. скор.: {int(event.value)}")
            
            manager.process_events(event)

        manager.update(time_delta)

        if transparent_bg:
            screen.fill((0, 0, 0, 0))
        else:
            screen.fill(BACKGROUND_COLOR)

        if sentence_manager is not None:
            sentence_manager.update(current_time, time_delta, 
                                    motion_speed_slider.get_current_value(), 
                                    rotation_speed_slider.get_current_value())
            sentence_manager.draw(screen)
            
            if not animation_complete and sentence_manager.is_complete():
                animation_complete = True
                status_label.set_text("Анимация завершена!")

        manager.draw_ui(screen)
        pygame.draw.rect(screen, current_text_color, color_preview_rect)
        pygame.draw.rect(screen, (255, 255, 255), color_preview_rect, 1)
        
        pygame.display.flip()

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
