from abc import ABC
from server.config.config import load_config
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class SingletonService(ABC):
    """
    Singleton service base class for services requiring singleton pattern
    """
    _instances = {}
    _config = None

    @classmethod
    def get_config(cls):
        """Load global configuration"""
        if cls._config is None:
            cls._config = load_config()
            logger.info("Configuration loaded successfully")
        return cls._config

    def __new__(cls, *args, **kwargs):
        if cls not in cls._instances:
            logger.info(f"Creating new instance of {cls.__name__}")
            cls._instances[cls] = super(SingletonService, cls).__new__(cls)
            # Add initialization flag
            cls._instances[cls]._initialized = False
        else:
            logger.info(f"Returning existing instance of {cls.__name__}")
        return cls._instances[cls]

    def __init__(self, *args, **kwargs):
        # Ensure initialization runs only once
        if not self._initialized:
            logger.info(f"{self.__class__.__name__}: Starting initialization")
            self.config = self.get_config()
            self._initialize(*args, **kwargs)
            self._initialized = True
            logger.info(f"{self.__class__.__name__}: Initialization completed")
        else:
            logger.info(
                f"{self.__class__.__name__}: Already initialized, skipping")

    def _initialize(self, *args, **kwargs):
        """
        Initialization method, subclasses should override for custom logic
        """
        pass
