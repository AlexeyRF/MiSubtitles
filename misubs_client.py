import pygame
import sys
import math
import random
import json
import os
import socket
import threading
import tkinter as tk
from tkinter import ttk, filedialog

if os.name == 'nt':
    import win32api
    import win32con
    import win32gui

CONFIG_FILE = "config_client.json"
DEFAULT_CONFIG = {
    "pos_x": 100,
    "pos_y": 100,
    "font_size": 60,
    "window_width": 800,
    "window_height": 300,
    "max_line_length": 40,
    "socket_host": "127.0.0.1",
    "socket_port": 12345
}

CHROMAKEY = (0, 0, 0)

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
        thickness = max(1, int(6 * alpha))
        tail_length = 0.06
        end_x = self.x - self.vx * tail_length
        end_y = self.y - self.vy * tail_length
        pygame.draw.line(screen, self.color, (int(self.x), int(self.y)), (int(end_x), int(end_y)), thickness)

def create_sparks(x, y, color, count=40, life=0.8, min_speed=100, max_speed=300):
    new_sparks = []
    for _ in range(int(count)):
        angle = random.uniform(math.pi + 0.2, 2 * math.pi - 0.2)
        speed = random.uniform(min_speed, max_speed)
        vx = math.cos(angle) * speed
        vy = math.sin(angle) * speed
        new_sparks.append(Spark(x, y, vx, vy, life * random.uniform(0.5, 1.5), color))
    return new_sparks

class FallingLetter:
    def __init__(self, letter_surf, center_x, center_y, color):
        self.active = True
        self.original_surf = letter_surf
        self.x = float(center_x)
        self.y = float(center_y)
        self.base_vx = random.uniform(-180, 180)
        self.base_vy = random.uniform(-280, -80)
        self.gravity = 500.0
        self.rz = 0.0
        self.rz_speed = random.uniform(-150, 150)
        self.start_time = pygame.time.get_ticks() / 1000.0
        self.shrink_duration = 1.5
        self.shrink_scale = 1.0
        self.color = color

    def update(self, current_time, dt):
        if not self.active:
            return
        elapsed = current_time - self.start_time
        progress = min(1.0, elapsed / self.shrink_duration)
        self.shrink_scale = 1.0 - progress
        if progress >= 1.0:
            self.active = False
            return
        self.x += self.base_vx * dt
        self.y += self.base_vy * dt
        self.base_vy += self.gravity * dt
        self.rz += self.rz_speed * dt

    def draw(self, screen):
        if not self.active:
            return
        orig_w, orig_h = self.original_surf.get_size()
        new_w, new_h = max(1, int(orig_w * self.shrink_scale)), max(1, int(orig_h * self.shrink_scale))
        scaled = pygame.transform.scale(self.original_surf, (new_w, new_h))
        rotated = pygame.transform.rotate(scaled, self.rz)
        rect = rotated.get_rect(center=(int(self.x), int(self.y)))
        screen.blit(rotated, rect)

class LetterItem:
    def __init__(self, char, surf_n, surf_w, color, x, y, target_x, target_y, appear_delay):
        self.char = char
        self.surf_n = surf_n
        self.surf_w = surf_w
        self.color = color
        self.x = x
        self.y = y
        self.target_x = target_x
        self.target_y = target_y
        self.appear_delay = appear_delay
        self.color_progress = 0.0

class SubtitleManager:
    def __init__(self, font_size, screen_w, screen_h, pos_x, pos_y, max_line_length=40):
        self.font = pygame.font.Font(None, font_size)
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.pos_x = pos_x
        self.pos_y = pos_y
        self.max_line_length = max_line_length
        
        self.current_letters = []
        self.pending_destruction = []
        self.falling_letters = []
        self.sparks = []
        self.char_cache = {}
        
        self.current_text = ""

    def render_char(self, char):
        if char in self.char_cache:
            return self.char_cache[char]

        color_normal = (255, 220, 100)
        color_white = (255, 255, 255)
        outline_color = (255, 255, 255)
        out_w = 2
        
        base_normal = self.font.render(char, True, color_normal)
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
        
        self.char_cache[char] = (surf_n, surf_w, color_normal)
        return surf_n, surf_w, color_normal

    def wrap_text(self, text):
        if len(text) <= self.max_line_length:
            return [text]
        
        lines = []
        current_line = ""
        for char in text:
            test_line = current_line + char
            if len(test_line) <= self.max_line_length:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = char
        if current_line:
            lines.append(current_line)
        
        if len(lines) > 3:
            lines = lines[:3]
            lines[-1] += "..."
        return lines

    def clear_all_letters(self):
        delay_step = 0.03
        current_delay = 0.0
        for item in self.current_letters:
            self.pending_destruction.append({
                'surf': item.surf_n,
                'x': item.x,
                'y': item.y,
                'delay': current_delay,
                'color': item.color
            })
            current_delay += delay_step
        self.current_letters = []

    def set_text(self, text):
        if self.current_text == text:
            return
            
        self.current_text = text
        
        if not text:
            self.clear_all_letters()
            return
        
        lines = self.wrap_text(text)
        self.clear_all_letters()
        
        line_height = self.font.get_height() + 10
        total_height = len(lines) * line_height
        start_y = self.screen_h - self.pos_y - total_height
        
        all_letters = []
        
        for line_idx, line_text in enumerate(lines):
            line_surfs = []
            line_widths = []
            for char in line_text:
                if char != " ":
                    surf_n, surf_w, color = self.render_char(char)
                    line_surfs.append((char, surf_n, surf_w, color))
                    line_widths.append(surf_w.get_width())
                else:
                    space_width = self.font.size(" ")[0]
                    empty_surf = pygame.Surface((space_width, 1), pygame.SRCALPHA)
                    line_surfs.append((' ', empty_surf, empty_surf, (255, 220, 100)))
                    line_widths.append(space_width)
            
            total_width = sum(line_widths)
            start_x = self.screen_w - total_width - self.pos_x
            current_x = start_x
            
            for i, (char, surf_n, surf_w, color) in enumerate(line_surfs):
                if char != ' ':
                    center_x = current_x + line_widths[i] / 2
                    center_y = start_y + line_idx * line_height + self.font.get_height() / 2
                    appear_delay = line_idx * 0.1 + i * 0.04
                    letter = LetterItem(
                        char, surf_n, surf_w, color,
                        center_x + 15, center_y,
                        center_x, center_y,
                        appear_delay
                    )
                    all_letters.append(letter)
                current_x += line_widths[i]
        
        self.current_letters = all_letters

    def update(self, current_time, dt):
        for pd in self.pending_destruction[:]:
            pd['delay'] -= dt
            if pd['delay'] <= 0:
                self.falling_letters.append(FallingLetter(
                    pd['surf'], pd['x'], pd['y'], pd.get('color', (255, 220, 100))
                ))
                self.sparks.extend(create_sparks(
                    pd['x'], pd['y'], pd.get('color', (255, 220, 100)), count=30
                ))
                self.pending_destruction.remove(pd)
                
        for fl in self.falling_letters[:]:
            fl.update(current_time, dt)
            if not fl.active:
                self.falling_letters.remove(fl)
                
        for sp in self.sparks[:]:
            sp.update(dt)
            if not sp.is_alive():
                self.sparks.remove(sp)
                
        move_speed = 12.0
        for item in self.current_letters:
            if item.appear_delay > 0:
                item.appear_delay -= dt
                continue
            item.x += (item.target_x - item.x) * move_speed * dt
            item.y += (item.target_y - item.y) * move_speed * dt
            if item.color_progress < 1.0:
                item.color_progress += 3.0 * dt
                if item.color_progress > 1.0:
                    item.color_progress = 1.0

    def draw(self, screen):
        for pd in self.pending_destruction:
            surf = pd['surf']
            rect = surf.get_rect(center=(int(pd['x']), int(pd['y'])))
            screen.blit(surf, rect)

        for fl in self.falling_letters:
            fl.draw(screen)
        for sp in self.sparks:
            sp.draw(screen)
            
        for item in self.current_letters:
            if item.appear_delay > 0 or item.char == ' ':
                continue
            w, h = item.surf_w.get_size()
            pos_x = int(item.x) - w // 2
            pos_y = int(item.y) - h // 2
            screen.blit(item.surf_w, (pos_x, pos_y))
            if item.color_progress > 0.0:
                clip_w = int(w * item.color_progress)
                if clip_w > 0:
                    clip_rect = pygame.Rect(0, 0, clip_w, h)
                    screen.blit(item.surf_n, (pos_x, pos_y), area=clip_rect)

# ========== SOCKET CLIENT ==========
class SocketClient:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.socket = None
        self.running = False
        self.text_queue = []
        
    def connect(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            self.running = True
            return True
        except Exception as e:
            print(f"Ошибка подключения к серверу: {e}")
            return False
    
    def receive_messages(self):
        buffer = ""
        while self.running:
            try:
                self.socket.settimeout(0.1)
                data = self.socket.recv(4096).decode('utf-8')
                if data:
                    buffer += data
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        if line.strip():
                            try:
                                message = json.loads(line)
                                if message.get('type') == 'text':
                                    self.text_queue.append(message.get('content', ''))
                            except json.JSONDecodeError:
                                print(f"Ошибка парсинга JSON: {line}")
            except socket.timeout:
                pass
            except (ConnectionResetError, BrokenPipeError):
                print("Соединение с сервером потеряно")
                self.running = False
                break
            except Exception as e:
                print(f"Ошибка приема данных: {e}")
                break
    
    def get_text(self):
        if self.text_queue:
            return self.text_queue.pop(0)
        return None
    
    def close(self):
        self.running = False
        if self.socket:
            self.socket.close()

def run_configurator():
    config = DEFAULT_CONFIG.copy()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                saved_config = json.load(f)
                config.update(saved_config)
        except:
            pass

    root = tk.Tk()
    root.title("Настройки субтитров (Клиент)")
    root.geometry("550x650")
    
    tk.Label(root, text="КЛИЕНТ ОТРИСОВКИ СУБТИТРОВ", font=("Arial", 12, "bold"), fg="blue").pack(pady=10)
    
    tk.Label(root, text="Настройки подключения к серверу:").pack(pady=5)
    
    tk.Label(root, text="Хост сервера:").pack(pady=5)
    host_var = tk.StringVar(value=config["socket_host"])
    tk.Entry(root, textvariable=host_var, width=30).pack()
    
    tk.Label(root, text="Порт сервера:").pack(pady=5)
    port_var = tk.IntVar(value=config["socket_port"])
    tk.Entry(root, textvariable=port_var, width=30).pack()
    
    tk.Label(root, text="Размер шрифта:").pack(pady=5)
    font_var = tk.IntVar(value=config["font_size"])
    tk.Scale(root, variable=font_var, from_=20, to=150, orient='horizontal').pack()
    
    tk.Label(root, text="Отступ справа (px):").pack(pady=5)
    x_var = tk.IntVar(value=config["pos_x"])
    tk.Entry(root, textvariable=x_var).pack()

    tk.Label(root, text="Отступ снизу (px):").pack(pady=5)
    y_var = tk.IntVar(value=config["pos_y"])
    tk.Entry(root, textvariable=y_var).pack()
    
    tk.Label(root, text="Ширина окна субтитров (px):").pack(pady=5)
    w_var = tk.IntVar(value=config.get("window_width", 800))
    tk.Entry(root, textvariable=w_var).pack()
    
    tk.Label(root, text="Высота окна субтитров (px):").pack(pady=5)
    h_var = tk.IntVar(value=config.get("window_height", 300))
    tk.Entry(root, textvariable=h_var).pack()
    
    tk.Label(root, text="Максимальная длина строки (символов):").pack(pady=5)
    line_var = tk.IntVar(value=config.get("max_line_length", 40))
    tk.Entry(root, textvariable=line_var).pack()

    def save_and_start():
        config["font_size"] = font_var.get()
        config["pos_x"] = x_var.get()
        config["pos_y"] = y_var.get()
        config["window_width"] = w_var.get()
        config["window_height"] = h_var.get()
        config["max_line_length"] = line_var.get()
        config["socket_host"] = host_var.get()
        config["socket_port"] = port_var.get()
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f)
        root.destroy()

    tk.Button(root, text="Запустить субтитры", command=save_and_start, bg="green", fg="white", font=("Arial", 12)).pack(pady=20)
    root.mainloop()
    return config

def set_window_topmost(hwnd):
    if os.name == 'nt':
        win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0,
                              win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW)

def main():
    config = run_configurator()
    
    client = SocketClient(config["socket_host"], config["socket_port"])
    if not client.connect():
        print("Не удалось подключиться к серверу. Убедитесь, что сервер запущен.")
        input("Нажмите Enter для выхода...")
        sys.exit()

    receive_thread = threading.Thread(target=client.receive_messages, daemon=True)
    receive_thread.start()
    
    pygame.init()
    
    info = pygame.display.Info()
    screen_width = info.current_w
    screen_height = info.current_h
    
    window_width = config.get("window_width", 800)
    window_height = config.get("window_height", 300)
    window_x = (screen_width - window_width) // 2
    window_y = screen_height - window_height - 50
    
    os.environ['SDL_VIDEO_WINDOW_POS'] = f"{window_x},{window_y}"
    screen = pygame.display.set_mode((window_width, window_height), pygame.NOFRAME)
    pygame.display.set_caption("Transparent Subtitles Client")
    
    if os.name == 'nt':
        hwnd = pygame.display.get_wm_info()["window"]
        styles = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE,
                               styles | win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT | win32con.WS_EX_TOPMOST)
        win32gui.SetLayeredWindowAttributes(hwnd, win32api.RGB(*CHROMAKEY), 0, win32con.LWA_COLORKEY)
        set_window_topmost(hwnd)

    clock = pygame.time.Clock()
    manager = SubtitleManager(
        config["font_size"],
        window_width,
        window_height,
        config["pos_x"],
        config["pos_y"],
        config.get("max_line_length", 40)
    )
    manager.set_text("Ожидание подключения к серверу...")

    current_display_text = None
    display_start_time = 0
    DISPLAY_DURATION = 5000 

    running = True
    
    while running:
        dt = clock.tick(60) / 1000.0
        current_time_ms = pygame.time.get_ticks()
        current_time_sec = current_time_ms / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_F12:
                    current_display_text = None
                    manager.set_text("")
                    while client.get_text():
                        pass

        new_text = client.get_text()
        if new_text and not new_text.startswith("Ошибка"):
            current_display_text = new_text
            display_start_time = current_time_ms
            manager.set_text(new_text)
        elif new_text and new_text.startswith("Ошибка"):
            manager.set_text(new_text[:50])
            current_display_text = None

        if current_display_text is not None and (current_time_ms - display_start_time) > DISPLAY_DURATION:
            manager.set_text("")
            current_display_text = None

        screen.fill(CHROMAKEY)
        try:
            manager.update(current_time_sec, dt)
            manager.draw(screen)
        except Exception as e:
            print(f"Ошибка отрисовки: {e}")
            pygame.time.wait(100)

        pygame.display.flip()

    client.close()
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
