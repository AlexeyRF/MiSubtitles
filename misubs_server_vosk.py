import sys
import json
import os
import queue
import threading
import socket
import time
import sounddevice as sd
from vosk import Model, KaldiRecognizer

CONFIG_FILE = "config_server.json"
DEFAULT_CONFIG = {
    "model_path": "model",
    "punctuation_model": "",
    "socket_port": 12345
}

audio_queue = queue.Queue()

def audio_callback(indata, frames, time, status):
    if status:
        print(status, file=sys.stderr)
    audio_queue.put(bytes(indata))

def vosk_worker(config, text_queue):
    model_path = config.get("model_path", "model")
    if not os.path.exists(model_path):
        text_queue.put("ОШИБКА: Модель Vosk не найдена!")
        return

    model = Model(model_path)
    samplerate = 16000
    rec = KaldiRecognizer(model, samplerate)
    
    punct_path = config.get("punctuation_model", "")
    if punct_path and os.path.exists(punct_path):
        try:
            rec.SetPunctuation(punct_path)
            print("Модель пунктуации загружена")
        except Exception as e:
            print(f"Не удалось загрузить модель пунктуации: {e}")
    
    device_id = None

    try:
        with sd.RawInputStream(samplerate=samplerate, blocksize=8000, dtype='int16',
                               channels=1, callback=audio_callback, device=device_id):
            print("Распознавание речи запущено...")
            while True:
                data = audio_queue.get()
                if rec.AcceptWaveform(data):
                    res = json.loads(rec.Result())
                    text = res.get("text", "")
                    if text and len(text) > 1:
                        text_queue.put(text)
    except Exception as e:
        text_queue.put(f"Ошибка микрофона: {e}")

def save_config(config):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f)

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
    print("СЕРВЕР РАСПОЗНАВАНИЯ РЕЧИ Vosk")
    print("=" * 50)
    
    model_path = input(f"Путь к модели Vosk [{config['model_path']}]: ").strip()
    if model_path:
        config['model_path'] = model_path
    
    punct_path = input(f"Путь к модели пунктуации (Enter для пропуска) [{config['punctuation_model']}]: ").strip()
    if punct_path:
        config['punctuation_model'] = punct_path
    
    port = input(f"Порт для сокета [{config['socket_port']}]: ").strip()
    if port:
        config['socket_port'] = int(port)
    
    save_config(config)
    
    text_queue = queue.Queue()
    
    recognizer_thread = threading.Thread(target=vosk_worker, args=(config, text_queue), daemon=True)
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