import os
import tempfile
import subprocess
import requests
from yt_dlp import YoutubeDL
from aiogram.types import File as TelegramFile

class FileHandler:
    def __init__(self, bot=None):
        self.bot = bot

    def download_from_url(self, url: str) -> tuple:
        """
        Скачивает файл по ссылке (YouTube, VK, прямые mp3/mp4 и др.) и возвращает (путь к файлу, имя/титул).
        """
        ydl_opts = {
            'outtmpl': '/tmp/%(title)s.%(ext)s',
            'format': 'bestvideo+bestaudio/best',
            'quiet': True,
            'ignoreerrors': True,
        }
        print(f"[LOG] outtmpl: {ydl_opts['outtmpl']}")
        if any(url.lower().endswith(ext) for ext in ['.mp3', '.mp4', '.wav', '.m4a', '.ogg']):
            # Прямая ссылка на файл
            response = requests.get(url, stream=True)
            ext = url.split('.')[-1].split('?')[0]
            fd, path = tempfile.mkstemp(suffix=f'.{ext}')
            print(f"[LOG] mkstemp path: {path}")
            with os.fdopen(fd, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            title = os.path.splitext(os.path.basename(url.split('?')[0]))[0]
            print(f"[LOG] Файл скачан: {path}, title: {title}")
            return path, title
        else:
            # YouTube, VK и др. через yt-dlp с fallback-стратегиями
            from yt_dlp.utils import DownloadError
            attempts = [
                ('bestvideo+bestaudio/best', 'основной способ'),
                ('bestaudio', 'только аудио'),
                ('bestvideo', 'только видео'),
            ]
            # Пробуем каждый формат только по одному разу
            for fmt, descr in attempts:
                ydl_opts['format'] = fmt
                print(f"[LOG] yt-dlp попытка: {descr} (format={fmt})")
                try:
                    with YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(url, download=True)
                        file_path = ydl.prepare_filename(info)
                        print(f"[LOG] YoutubeDL file_path: {file_path}")
                        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                            title = info.get('title') or os.path.splitext(os.path.basename(file_path))[0]
                            print(f"[LOG] Файл успешно скачан: {file_path}, title: {title}")
                            return file_path, title
                        else:
                            print(f"[ERROR] Файл не создан или пустой: {file_path}")
                except DownloadError as e:
                    print(f"[ERROR] yt-dlp DownloadError ({descr}): {e}")
                except Exception as e:
                    print(f"[ERROR] yt-dlp Exception ({descr}): {e}")
            print(f"[ERROR] Не удалось скачать файл с {url} ни одним способом!")
            return None, None

    async def download(self, file_obj: TelegramFile, file_ext: str) -> str:
        """Скачивает файл из Telegram и возвращает путь к файлу."""
        if not self.bot:
            raise RuntimeError('Bot instance required for Telegram file download')
        file = await self.bot.get_file(file_obj.file_id)
        fd, path = tempfile.mkstemp(suffix=f'.{file_ext}')
        print(f"[LOG] mkstemp path (Telegram): {path}")
        with os.fdopen(fd, 'wb') as f:
            await self.bot.download_file(file.file_path, f)
        print(f"[LOG] Файл скачан из Telegram: {path}")
        return path

    def get_duration(self, file_path: str) -> float:
        """Возвращает длительность файла в секундах (через ffprobe)."""
        try:
            result = subprocess.run([
                'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1', file_path
            ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            return float(result.stdout)
        except Exception:
            return 0.0

    def convert_video_to_audio(self, file_path: str) -> str:
        """Конвертирует видеофайл в аудио (wav) через ffmpeg и возвращает путь к новому файлу."""
        out_path = tempfile.mktemp(suffix='.wav')
        print(f"[LOG] mktemp out_path (convert_video_to_audio): {out_path}")
        subprocess.run([
            'ffmpeg', '-i', file_path, '-vn', '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1', out_path,
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(f"[LOG] Файл сконвертирован: {out_path}")
        return out_path 