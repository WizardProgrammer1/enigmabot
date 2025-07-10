import os
import logging
import tempfile
import json
import requests
from typing import Optional, Dict, Any
from src.config import Config

class TranscriptionProvider:
    """Базовый класс для провайдеров транскрипции"""
    
    def transcribe(self, file_path: str, language: str = 'ru') -> str:
        """Основной метод транскрипции"""
        raise NotImplementedError

    def transcribe_with_timestamps(self, file_path: str, language: str = 'ru') -> dict:
        """Транскрипция с таймкодами (по умолчанию просто текст)"""
        return {"text": self.transcribe(file_path, language), "segments": []}

class WhisperLocalProvider(TranscriptionProvider):
    """Локальный Whisper с максимальным качеством"""
    
    def __init__(self):
        import whisper
        import torch
        
        device = "cuda:0" if torch.cuda.is_available() else "cpu"
        logging.info(f"Whisper Local: Используется устройство {device}")
        
        self.model = whisper.load_model(Config.WHISPER_MODEL, device=device)
        logging.info(f"Whisper Local: Модель {Config.WHISPER_MODEL} загружена")
    
    def transcribe(self, file_path: str, language: str = 'ru') -> str:
        options = Config.WHISPER_OPTIONS.copy()
        if language and language != 'other':
            options['language'] = language
        options['task'] = 'transcribe'
        
        result = self.model.transcribe(file_path, **options)
        return result['text']

class OpenAIWhisperProvider(TranscriptionProvider):
    """OpenAI Whisper API - максимальное качество"""
    
    def __init__(self):
        if not Config.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY не установлен")
        self.api_key = Config.OPENAI_API_KEY
    
    def transcribe(self, file_path: str, language: str = 'ru') -> str:
        import openai
        
        client = openai.OpenAI(api_key=self.api_key)
        
        with open(file_path, 'rb') as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language=language if language != 'other' else None,
                response_format="text"
            )
        
        return transcript

class GoogleSpeechProvider(TranscriptionProvider):
    """Google Speech-to-Text API с поддержкой таймкодов и загрузкой больших файлов в GCS"""
    
    def __init__(self):
        if not Config.GOOGLE_CLOUD_CREDENTIALS:
            raise ValueError("GOOGLE_CLOUD_CREDENTIALS не установлен")
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = Config.GOOGLE_CLOUD_CREDENTIALS
        self.bucket_name = os.getenv('GOOGLE_CLOUD_STORAGE_BUCKET')
        if not self.bucket_name:
            raise ValueError("GOOGLE_CLOUD_STORAGE_BUCKET не установлен в .env (имя бакета для хранения аудиофайлов)")
    
    def transcribe(self, file_path: str, language: str = 'ru') -> str:
        result = self.transcribe_with_timestamps(file_path, language)
        return result["text"]

    def transcribe_with_timestamps(self, file_path: str, language: str = 'ru') -> dict:
        from google.cloud import speech
        from google.cloud import storage
        import math
        client = speech.SpeechClient()
        
        # Читаем аудиофайл
        with open(file_path, "rb") as audio_file:
            content = audio_file.read()
        file_size = len(content)
        
        language_code = 'ru-RU' if language == 'ru' else 'en-US'
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code=language_code,
            enable_automatic_punctuation=True,
            enable_word_time_offsets=True,
            model="latest_long"
        )
        
        # Google ограничивает recognize и long_running_recognize до 10 МБ для content
        if file_size <= 10 * 1024 * 1024:
            audio = speech.RecognitionAudio(content=content)
            response = client.recognize(config=config, audio=audio)
        else:
            # Загружаем файл в Google Cloud Storage
            storage_client = storage.Client()
            bucket = storage_client.bucket(self.bucket_name)
            blob_name = os.path.basename(file_path)
            blob = bucket.blob(blob_name)
            blob.upload_from_filename(file_path)
            gcs_uri = f"gs://{self.bucket_name}/{blob_name}"
            audio = speech.RecognitionAudio(uri=gcs_uri)
            operation = client.long_running_recognize(config=config, audio=audio)
            response = operation.result(timeout=1200)
            # После распознавания удаляем файл из GCS
            blob.delete()
        
        # Собираем текст и сегменты с таймкодами
        full_text = ""
        segments = []
        for result in response.results:
            alternative = result.alternatives[0]
            full_text += alternative.transcript + " "
            for word_info in alternative.words:
                start = word_info.start_time.total_seconds()
                end = word_info.end_time.total_seconds()
                text = word_info.word
                segments.append({
                    "start": start,
                    "end": end,
                    "text": text
                })
        return {"text": full_text.strip(), "segments": segments}

class AzureSpeechProvider(TranscriptionProvider):
    """Azure Speech Services"""
    
    def __init__(self):
        if not Config.AZURE_SPEECH_KEY or not Config.AZURE_SPEECH_REGION:
            raise ValueError("AZURE_SPEECH_KEY и AZURE_SPEECH_REGION должны быть установлены")
        
        self.speech_key = Config.AZURE_SPEECH_KEY
        self.service_region = Config.AZURE_SPEECH_REGION
    
    def transcribe(self, file_path: str, language: str = 'ru') -> str:
        import azure.cognitiveservices.speech as speechsdk
        
        # Настройка конфигурации
        speech_config = speechsdk.SpeechConfig(
            subscription=self.speech_key, 
            region=self.service_region
        )
        
        # Настройка языка
        language_code = 'ru-RU' if language == 'ru' else 'en-US'
        speech_config.speech_recognition_language = language_code
        
        # Настройка для максимального качества
        speech_config.speech_recognition_model_name = "latest_long"
        speech_config.enable_dictation()
        
        # Создание аудио конфигурации
        audio_config = speechsdk.audio.AudioConfig(filename=file_path)
        
        # Создание распознавателя
        speech_recognizer = speechsdk.SpeechRecognizer(
            speech_config=speech_config, 
            audio_config=audio_config
        )
        
        # Распознавание
        result = speech_recognizer.recognize_once_async().get()
        
        if result.reason == speechsdk.ResultReason.RecognizedSpeech:
            return result.text
        else:
            raise Exception(f"Ошибка распознавания: {result.reason}")

class AssemblyAIProvider(TranscriptionProvider):
    """AssemblyAI - специализированные модели для разных типов контента"""
    
    def __init__(self):
        if not Config.ASSEMBLYAI_API_KEY:
            raise ValueError("ASSEMBLYAI_API_KEY не установлен")
        
        self.api_key = Config.ASSEMBLYAI_API_KEY
        self.base_url = "https://api.assemblyai.com/v2"
    
    def transcribe(self, file_path: str, language: str = 'ru') -> str:
        headers = {
            "authorization": self.api_key,
            "content-type": "application/json"
        }
        
        # Загружаем файл
        with open(file_path, "rb") as f:
            response = requests.post(
                f"{self.base_url}/upload",
                headers=headers,
                data=f
            )
        
        upload_url = response.json()["upload_url"]
        
        # Настройки транскрипции для максимального качества
        transcript_request = {
            "audio_url": upload_url,
            "language_code": "ru" if language == 'ru' else "en",
            "punctuate": True,
            "format_text": True,
            "speaker_labels": True,
            "diarization": True,
            "boost_param": "high",
            "auto_highlights": True,
            "entity_detection": True,
            "auto_chapters": True
        }
        
        # Запускаем транскрипцию
        response = requests.post(
            f"{self.base_url}/transcript",
            json=transcript_request,
            headers=headers
        )
        
        transcript_id = response.json()["id"]
        
        # Ждем завершения
        while True:
            polling_response = requests.get(
                f"{self.base_url}/transcript/{transcript_id}",
                headers=headers
            )
            
            polling_response = polling_response.json()
            
            if polling_response["status"] == "completed":
                return polling_response["text"]
            elif polling_response["status"] == "error":
                raise Exception(f"Ошибка AssemblyAI: {polling_response['error']}")
            
            import time
            time.sleep(3)

class TranscriptionFactory:
    """Фабрика для создания провайдеров транскрипции"""
    
    @staticmethod
    def create_provider(provider_name: str = None) -> TranscriptionProvider:
        """Создает провайдер транскрипции по имени"""
        
        provider_name = provider_name or Config.TRANSCRIPTION_PROVIDER
        
        providers = {
            'whisper_local': WhisperLocalProvider,
            'openai': OpenAIWhisperProvider,
            'google': GoogleSpeechProvider,
            'azure': AzureSpeechProvider,
            'assemblyai': AssemblyAIProvider
        }
        
        if provider_name not in providers:
            raise ValueError(f"Неизвестный провайдер: {provider_name}")
        
        return providers[provider_name]()
    
    @staticmethod
    def get_available_providers() -> Dict[str, str]:
        """Возвращает список доступных провайдеров с описанием"""
        return {
            'whisper_local': 'Локальный Whisper (бесплатно, высокое качество)',
            'openai': 'OpenAI Whisper API (платно, максимальное качество)',
            'google': 'Google Speech-to-Text (платно, отличная поддержка русского)',
            'azure': 'Azure Speech Services (платно, интеграция с Microsoft)',
            'assemblyai': 'AssemblyAI (платно, специализированные модели)'
        } 