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
            'outtmpl': tempfile.mktemp(suffix='.%(ext)s'),
            'format': 'bestaudio/best',
            'quiet': True,
        }
        if any(url.lower().endswith(ext) for ext in ['.mp3', '.mp4', '.wav', '.m4a', '.ogg']):
            # Прямая ссылка на файл
            response = requests.get(url, stream=True)
            ext = url.split('.')[-1].split('?')[0]
            fd, path = tempfile.mkstemp(suffix=f'.{ext}')
            with os.fdopen(fd, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            title = os.path.splitext(os.path.basename(url.split('?')[0]))[0]
            return path, title
        else:
            # YouTube, VK и др. через yt-dlp
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                file_path = ydl.prepare_filename(info)
                title = info.get('title') or os.path.splitext(os.path.basename(file_path))[0]
                return file_path, title

    async def download(self, file_obj: TelegramFile, file_ext: str) -> str:
        """Скачивает файл из Telegram и возвращает путь к файлу."""
        if not self.bot:
            raise RuntimeError('Bot instance required for Telegram file download')
        file = await self.bot.get_file(file_obj.file_id)
        fd, path = tempfile.mkstemp(suffix=f'.{file_ext}')
        with os.fdopen(fd, 'wb') as f:
            await self.bot.download_file(file.file_path, f)
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
        subprocess.run([
            'ffmpeg', '-i', file_path, '-vn', '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1', out_path,
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return out_path 