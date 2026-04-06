import pygame
import sys
import math
import random
import json
import os
import socket
import threading
import tkinter as tk
from tkinter import ttk, filedialog, colorchooser

if os.name == 'nt':
    import win32api
    import win32con
    import win32gui

CONFIG_FILE = "config_client.json"
DEFAULT_CONFIG = {
    "pos_x": 50,
    "pos_y": 50,
    "font_size": 60,
    "font_name": "arial",
    "font_color": "#FFDC64",
    "enable_sparks": True,
    "screen_position": "Снизу по центру",
    "window_width": 1000,
    "window_height": 400,
    "max_line_length": 50,
    "socket_host": "127.0.0.1",
    "socket_port": 12345,
    "normal_window": False,
    "antialias": True,
    "num_slots": 5,
    "line_spacing": 10  
}

CHROMAKEY = (0, 0, 0)

def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

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
        self.local_y = 0.0  

class SubtitleManager:
    def __init__(self, font_size, screen_w, screen_h, pos_x, pos_y, max_line_length, font_name, font_color, enable_sparks, screen_position, antialias, num_slots, line_spacing):
        try:
            self.font = pygame.font.SysFont(font_name, font_size)
        except:
            self.font = pygame.font.Font(None, font_size)
            
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.pos_x = pos_x
        self.pos_y = pos_y
        self.max_line_length = max_line_length
        self.font_color = hex_to_rgb(font_color)
        self.enable_sparks = enable_sparks
        self.screen_position = screen_position
        self.antialias = antialias
        self.num_slots = max(1, num_slots)
        self.line_spacing = line_spacing 
        
        self.messages = [] 
        self.pending_destruction = []
        self.falling_letters = []
        self.sparks = []
        self.char_cache = {}

    def render_char(self, char):
        if char in self.char_cache:
            return self.char_cache[char]

        color_normal = self.font_color
        color_white = (255, 255, 255)
        outline_color = (255, 255, 255)
        out_w = 2
        
        base_normal = self.font.render(char, self.antialias, color_normal)
        base_white = self.font.render(char, self.antialias, color_white)
        w, h = base_normal.get_size()
        
        surf_n = pygame.Surface((w + out_w * 2, h + out_w * 2), pygame.SRCALPHA)
        surf_w = pygame.Surface((w + out_w * 2, h + out_w * 2), pygame.SRCALPHA)
        
        for dx in [-out_w, 0, out_w]:
            for dy in [-out_w, 0, out_w]:
                if dx == 0 and dy == 0:
                    continue
                outline = self.font.render(char, self.antialias, outline_color)
                surf_n.blit(outline, (dx + out_w, dy + out_w))
                surf_w.blit(outline, (dx + out_w, dy + out_w))
                
        surf_n.blit(base_normal, (out_w, out_w))
        surf_w.blit(base_white, (out_w, out_w))
        
        self.char_cache[char] = (surf_n, surf_w, color_normal)
        return surf_n, surf_w, color_normal

    def wrap_text(self, text):
        max_pixels = max(100, self.screen_w - self.pos_x * 2) 
        
        lines = []
        current_line = ""
        for char in text:
            test_line = current_line + char
            test_width = self.font.size(test_line)[0]
            
            if len(test_line) <= self.max_line_length and test_width <= max_pixels:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = char
        if current_line:
            lines.append(current_line)
        
        if len(lines) > 4:
            lines = lines[:4]
            lines[-1] += "..."
        return lines

    def clear_oldest(self):
        if self.messages:
            msg = self.messages.pop(0)
            delay_step = 0.03
            current_delay = 0.0
            for item in msg['letters']:
                self.pending_destruction.append({
                    'surf': item.surf_n,
                    'x': item.x,
                    'y': item.y,
                    'delay': current_delay,
                    'color': item.color
                })
                current_delay += delay_step

    def clear_all(self):
        while self.messages:
            self.clear_oldest()

    def _recalculate_layout(self, is_new=False):
        if not self.messages:
            return
            
        gap_between_msgs = self.line_spacing * 2 
        total_stack_height = sum(msg['total_height'] for msg in self.messages) + gap_between_msgs * (len(self.messages) - 1)
        
        if "Сверху" in self.screen_position:
            current_y = self.pos_y
        elif "По центру" in self.screen_position and "Сверху" not in self.screen_position and "Снизу" not in self.screen_position:
            current_y = (self.screen_h - total_stack_height) // 2
        else: 
            current_y = self.screen_h - self.pos_y - total_stack_height
            
        for i, msg in enumerate(self.messages):
            for item in msg['letters']:
                item.target_y = current_y + item.local_y
                if is_new and i == len(self.messages) - 1 and item.y == 0:
                    item.y = item.target_y + 20 
            current_y += msg['total_height'] + gap_between_msgs

    def add_text(self, text, current_time_sec, duration=5.0):
        if not text:
            self.clear_all()
            return
        
        if len(self.messages) >= self.num_slots:
            self.clear_oldest()
        
        lines = self.wrap_text(text)
        line_height = self.font.get_height() + self.line_spacing
        total_height = len(lines) * line_height
        
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
                    line_surfs.append((' ', empty_surf, empty_surf, self.font_color))
                    line_widths.append(space_width)
            
            total_width = sum(line_widths)
            
            if "слева" in self.screen_position:
                start_x = self.pos_x
            elif "справа" in self.screen_position:
                start_x = self.screen_w - total_width - self.pos_x
            else:
                start_x = (self.screen_w - total_width) // 2
                
            current_x = start_x
            
            for i, (char, surf_n, surf_w, color) in enumerate(line_surfs):
                if char != ' ':
                    center_x = current_x + line_widths[i] / 2
                    local_y = line_idx * line_height + self.font.get_height() / 2
                    appear_delay = line_idx * 0.1 + i * 0.04
                    
                    letter = LetterItem(
                        char, surf_n, surf_w, color,
                        center_x + 15, 0,
                        center_x, 0,
                        appear_delay
                    )
                    letter.local_y = local_y
                    all_letters.append(letter)
                current_x += line_widths[i]
        
        new_msg = {
            'letters': all_letters,
            'expiration': current_time_sec + duration,
            'total_height': total_height
        }
        self.messages.append(new_msg)
        self._recalculate_layout(is_new=True)

    def update(self, current_time_sec, dt):
        expired = False
        while self.messages and current_time_sec >= self.messages[0]['expiration']:
            self.clear_oldest()
            expired = True
            
        if expired:
            self._recalculate_layout()

        for pd in self.pending_destruction[:]:
            pd['delay'] -= dt
            if pd['delay'] <= 0:
                self.falling_letters.append(FallingLetter(
                    pd['surf'], pd['x'], pd['y'], pd.get('color', self.font_color)
                ))
                if self.enable_sparks:
                    self.sparks.extend(create_sparks(
                        pd['x'], pd['y'], pd.get('color', self.font_color), count=30
                    ))
                self.pending_destruction.remove(pd)
                
        for fl in self.falling_letters[:]:
            fl.update(current_time_sec, dt)
            if not fl.active:
                self.falling_letters.remove(fl)
                
        for sp in self.sparks[:]:
            sp.update(dt)
            if not sp.is_alive():
                self.sparks.remove(sp)
                
        move_speed = 12.0
        for msg in self.messages:
            for item in msg['letters']:
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
            
        for msg in self.messages:
            for item in msg['letters']:
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
    pygame.font.init()
    sys_fonts = pygame.font.get_fonts()
    sys_fonts.sort()

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
    root.geometry("600x950") 
    
    tk.Label(root, text="КЛИЕНТ ОТРИСОВКИ СУБТИТРОВ", font=("Arial", 12, "bold"), fg="blue").pack(pady=10)
    tk.Label(root, text="Настройки подключения:", font=("Arial", 10, "bold")).pack(pady=5)
    
    host_frame = tk.Frame(root)
    host_frame.pack()
    tk.Label(host_frame, text="Хост:").pack(side=tk.LEFT)
    host_var = tk.StringVar(value=config["socket_host"])
    tk.Entry(host_frame, textvariable=host_var, width=15).pack(side=tk.LEFT, padx=5)
    tk.Label(host_frame, text="Порт:").pack(side=tk.LEFT)
    port_var = tk.IntVar(value=config["socket_port"])
    tk.Entry(host_frame, textvariable=port_var, width=10).pack(side=tk.LEFT)

    tk.Label(root, text="---", fg="gray").pack(pady=5)
    
    tk.Label(root, text="Внешний вид и анимация:", font=("Arial", 10, "bold")).pack(pady=5)

    tk.Label(root, text="Шрифт:").pack()
    font_name_var = tk.StringVar(value=config.get("font_name", "arial"))
    font_cb = ttk.Combobox(root, textvariable=font_name_var, values=sys_fonts, width=30)
    font_cb.pack()

    tk.Label(root, text="Размер шрифта:").pack(pady=5)
    font_var = tk.IntVar(value=config["font_size"])
    tk.Scale(root, variable=font_var, from_=20, to=150, orient='horizontal', length=200).pack()

    color_var = tk.StringVar(value=config.get("font_color", "#FFDC64"))
    def choose_color():
        color_code = colorchooser.askcolor(title="Выберите цвет текста", initialcolor=color_var.get())[1]
        if color_code:
            color_var.set(color_code)
            color_btn.config(bg=color_code)

    color_btn = tk.Button(root, text="Выбрать цвет текста", bg=color_var.get(), command=choose_color, width=20)
    color_btn.pack(pady=10)

    sparks_var = tk.BooleanVar(value=config.get("enable_sparks", True))
    tk.Checkbutton(root, text="Включить искры (анимация разрушения)", variable=sparks_var).pack(pady=2)
    
    antialias_var = tk.BooleanVar(value=config.get("antialias", True))
    tk.Checkbutton(root, text="Включить сглаживание шрифта", variable=antialias_var).pack(pady=2)

    tk.Label(root, text="---", fg="gray").pack(pady=5)

    tk.Label(root, text="Расположение на экране:", font=("Arial", 10, "bold")).pack(pady=5)

    pos_options = ["Снизу по центру", "Сверху по центру", "Снизу слева", "Снизу справа", "Сверху слева", "Сверху справа", "По центру"]
    pos_var = tk.StringVar(value=config.get("screen_position", "Снизу по центру"))
    ttk.Combobox(root, textvariable=pos_var, values=pos_options, state="readonly", width=25).pack()

    pos_frame = tk.Frame(root)
    pos_frame.pack(pady=10)
    tk.Label(pos_frame, text="Отступ X (px):").pack(side=tk.LEFT)
    x_var = tk.IntVar(value=config["pos_x"])
    tk.Entry(pos_frame, textvariable=x_var, width=8).pack(side=tk.LEFT, padx=10)
    
    tk.Label(pos_frame, text="Отступ Y (px):").pack(side=tk.LEFT)
    y_var = tk.IntVar(value=config["pos_y"])
    tk.Entry(pos_frame, textvariable=y_var, width=8).pack(side=tk.LEFT)

    tk.Label(root, text="---", fg="gray").pack(pady=5)
    
    tk.Label(root, text="Окно и параметры текста:", font=("Arial", 10, "bold")).pack(pady=5)
    
    normal_window_var = tk.BooleanVar(value=config.get("normal_window", False))
    tk.Checkbutton(root, text="Обычное окно (можно перемещать, без прозрачного фона)", variable=normal_window_var).pack(pady=2)

    win_frame = tk.Frame(root)
    win_frame.pack(pady=5)
    tk.Label(win_frame, text="Ширина окна:").pack(side=tk.LEFT)
    w_var = tk.IntVar(value=config.get("window_width", 1000))
    tk.Entry(win_frame, textvariable=w_var, width=8).pack(side=tk.LEFT, padx=10)
    
    tk.Label(win_frame, text="Высота окна:").pack(side=tk.LEFT)
    h_var = tk.IntVar(value=config.get("window_height", 300))
    tk.Entry(win_frame, textvariable=h_var, width=8).pack(side=tk.LEFT)
    
    slots_frame = tk.Frame(root)
    slots_frame.pack(pady=5)
    tk.Label(slots_frame, text="Макс. длина строки:").pack(side=tk.LEFT)
    line_var = tk.IntVar(value=config.get("max_line_length", 50))
    tk.Entry(slots_frame, textvariable=line_var, width=8).pack(side=tk.LEFT, padx=10)

    tk.Label(slots_frame, text="Кол-во слотов:").pack(side=tk.LEFT)
    slots_var = tk.IntVar(value=config.get("num_slots", 2))
    tk.Entry(slots_frame, textvariable=slots_var, width=8).pack(side=tk.LEFT)

    spacing_frame = tk.Frame(root)
    spacing_frame.pack(pady=5)
    tk.Label(spacing_frame, text="Интервал между строками (px):").pack(side=tk.LEFT)
    spacing_var = tk.IntVar(value=config.get("line_spacing", 10))
    tk.Entry(spacing_frame, textvariable=spacing_var, width=8).pack(side=tk.LEFT, padx=10)

    def save_and_start():
        config["font_size"] = font_var.get()
        config["font_name"] = font_name_var.get()
        config["font_color"] = color_var.get()
        config["enable_sparks"] = sparks_var.get()
        config["antialias"] = antialias_var.get()
        config["screen_position"] = pos_var.get()
        config["pos_x"] = x_var.get()
        config["pos_y"] = y_var.get()
        config["window_width"] = w_var.get()
        config["window_height"] = h_var.get()
        config["max_line_length"] = line_var.get()
        config["num_slots"] = slots_var.get()
        config["line_spacing"] = spacing_var.get() 
        config["socket_host"] = host_var.get()
        config["socket_port"] = port_var.get()
        config["normal_window"] = normal_window_var.get()
        
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4)
        root.destroy()

    tk.Button(root, text="Сохранить и запустить", command=save_and_start, bg="green", fg="white", font=("Arial", 12, "bold")).pack(pady=20)
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
    
    window_width = config.get("window_width", 1000)
    window_height = config.get("window_height", 300)
    screen_position = config.get("screen_position", "Снизу по центру")
    is_normal_window = config.get("normal_window", False)
    
    if "Сверху" in screen_position:
        window_y = 50
    elif "По центру" in screen_position and "Сверху" not in screen_position and "Снизу" not in screen_position:
        window_y = (screen_height - window_height) // 2
    else:
        window_y = screen_height - window_height - 50

    if "слева" in screen_position:
        window_x = 50
    elif "справа" in screen_position:
        window_x = screen_width - window_width - 50
    else:
        window_x = (screen_width - window_width) // 2
    
    os.environ['SDL_VIDEO_WINDOW_POS'] = f"{window_x},{window_y}"
    
    if is_normal_window:
        screen = pygame.display.set_mode((window_width, window_height))
    else:
        screen = pygame.display.set_mode((window_width, window_height), pygame.NOFRAME)
    
    pygame.display.set_caption("Transparent Subtitles Client")
    
    if os.name == 'nt' and not is_normal_window:
        hwnd = pygame.display.get_wm_info()["window"]
        styles = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE,
                               styles | win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT | win32con.WS_EX_TOPMOST)
        win32gui.SetLayeredWindowAttributes(hwnd, win32api.RGB(*CHROMAKEY), 0, win32con.LWA_COLORKEY)
        set_window_topmost(hwnd)

    clock = pygame.time.Clock()
    manager = SubtitleManager(
        font_size=config["font_size"],
        screen_w=window_width,
        screen_h=window_height,
        pos_x=config["pos_x"],
        pos_y=config["pos_y"],
        max_line_length=config.get("max_line_length", 50),
        font_name=config.get("font_name", "arial"),
        font_color=config.get("font_color", "#FFDC64"),
        enable_sparks=config.get("enable_sparks", True),
        screen_position=screen_position,
        antialias=config.get("antialias", True),
        num_slots=config.get("num_slots", 2),
        line_spacing=config.get("line_spacing", 10) 
    )
    
    manager.add_text("Ожидание подключения к серверу...", pygame.time.get_ticks() / 1000.0, 5.0)

    running = True
    
    while running:
        dt = clock.tick(60) / 1000.0
        current_time_sec = pygame.time.get_ticks() / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_F12:
                    manager.clear_all()
                    while client.get_text():
                        pass

        new_text = client.get_text()
        if new_text and not new_text.startswith("Ошибка"):
            manager.add_text(new_text, current_time_sec, 5.0)
        elif new_text and new_text.startswith("Ошибка"):
            manager.add_text(new_text[:50], current_time_sec, 5.0)

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
