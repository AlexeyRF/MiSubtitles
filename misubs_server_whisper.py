import sys
import json
import os
import queue
import threading
import socket
import time
import sounddevice as sd
import numpy as np
import whisper
import torch

CONFIG_FILE = "config_server_whisper.json"
DEFAULT_CONFIG = {
    "model_size": "base", 
    "language": "",       
    "energy_threshold": 0.02, 
    "socket_port": 12345
}

audio_queue = queue.Queue()

def audio_callback(indata, frames, time_info, status):
    if status:
        print(status, file=sys.stderr)
    audio_queue.put(indata.copy())

def whisper_worker(config, text_queue):
    model_size = config.get("model_size", "base")
    print(f"Загрузка модели Whisper '{model_size}'... (это может занять некоторое время)")
    
    try:
        model = whisper.load_model(model_size)
        print("Модель успешно загружена!")
    except Exception as e:
        text_queue.put(f"ОШИБКА: Не удалось загрузить модель Whisper! {e}")
        return

    samplerate = 16000
    energy_threshold = config.get("energy_threshold", 0.02)
    language = config.get("language", "")
    
    silence_duration_sec = 1.0  
    frames_per_buffer = 8000  
    
    buffer = []
    is_speaking = False
    silence_frames = 0
    use_fp16 = torch.cuda.is_available() 

    try:
        with sd.InputStream(samplerate=samplerate, blocksize=frames_per_buffer, dtype='float32',
                            channels=1, callback=audio_callback):
            print("Распознавание речи запущено. Жду вашего голоса...")
            while True:
                data = audio_queue.get()
                
                rms = np.sqrt(np.mean(data**2))
                
                if rms > energy_threshold:
                    is_speaking = True
                    silence_frames = 0
                    buffer.append(data)
                elif is_speaking:
                    silence_frames += len(data)
                    buffer.append(data)
                    
                    if silence_frames / samplerate > silence_duration_sec:
                        audio_data = np.concatenate(buffer).flatten()
                        
                        if len(audio_data) / samplerate > 0.5:
                            options = {"fp16": use_fp16}
                            if language:
                                options["language"] = language
                            
                            result = model.transcribe(audio_data, **options)
                            text = result.get("text", "").strip()
                            
                            if text:
                                text_queue.put(text)
                        
                        buffer = []
                        is_speaking = False
                        silence_frames = 0
    except Exception as e:
        text_queue.put(f"Ошибка микрофона/распознавания: {e}")

def save_config(config):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4)

def load_config():
    config = DEFAULT_CONFIG.copy()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                saved_config = json.load(f)
                config.update(saved_config)
        except:
            pass
    return config

def main():
    config = load_config()
    
    print("=" * 50)
    print("СЕРВЕР РАСПОЗНАВАНИЯ РЕЧИ OpenAI Whisper")
    print("=" * 50)
    
    model_size = input(f"Размер модели Whisper (tiny/base/small/medium/large) [{config['model_size']}]: ").strip()
    if model_size:
        config['model_size'] = model_size
        
    lang = input(f"Язык (например 'ru', Enter для автоопределения) [{config['language']}]: ").strip()
    config['language'] = lang 
    
    port = input(f"Порт для сокета [{config['socket_port']}]: ").strip()
    if port:
        config['socket_port'] = int(port)
    
    save_config(config)
    
    text_queue = queue.Queue()
    
    recognizer_thread = threading.Thread(target=whisper_worker, args=(config, text_queue), daemon=True)
    recognizer_thread.start()
    
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(('127.0.0.1', config['socket_port']))
    server_socket.listen(1)
    
    print(f"\nСервер запущен на порту {config['socket_port']}")
    print("Ожидание подключения клиента...")
    
    client_socket = None
    last_text = ""
    last_time = 0
    
    try:
        while True:
            if client_socket is None:
                try:
                    server_socket.settimeout(1.0)
                    client_socket, addr = server_socket.accept()
                    print(f"Клиент подключен: {addr}")
                    client_socket.settimeout(None)
                except socket.timeout:
                    pass
                except Exception as e:
                    print(f"Ошибка при подключении клиента: {e}")
            
            try:
                new_text = text_queue.get_nowait()
                if new_text:
                    current_time = time.time() * 1000
                    if new_text == last_text and (current_time - last_time) < 1000:
                        continue
                    last_text = new_text
                    last_time = current_time
                    
                    if client_socket:
                        try:
                            message = json.dumps({"type": "text", "content": new_text})
                            client_socket.send((message + "\n").encode('utf-8'))
                            print(f"Отправлено: {new_text}")
                        except (BrokenPipeError, ConnectionResetError):
                            print("Клиент отключился")
                            client_socket = None
            except queue.Empty:
                pass
            
            if client_socket:
                try:
                    client_socket.settimeout(0.1)
                    data = client_socket.recv(1024)
                    if not data:
                        print("Клиент отключился")
                        client_socket = None
                except socket.timeout:
                    pass
                except (ConnectionResetError, BrokenPipeError):
                    print("Клиент отключился")
                    client_socket = None
                finally:
                    if client_socket:
                        client_socket.settimeout(None)
            
            time.sleep(0.01)
            
    except KeyboardInterrupt:
        print("\nСервер остановлен")
    finally:
        if client_socket:
            client_socket.close()
        server_socket.close()

if __name__ == "__main__":
    main()
