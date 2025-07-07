import logging

class Logger:
    @staticmethod
    def setup(log_file: str = 'bot.log'):
        logger = logging.getLogger('TelegramBot')
        logger.setLevel(logging.INFO)
        formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s')

        # File handler
        fh = logging.FileHandler(log_file, encoding='utf-8')
        fh.setLevel(logging.INFO)
        fh.setFormatter(formatter)
        logger.addHandler(fh)

        # Console handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(formatter)
        logger.addHandler(ch)

        return logger 