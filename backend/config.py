import os
import sys


def _resolve_base_dir():
    """Resolve the project base directory reliably across environments.

    Handles Windows junctions, OneDrive shadow paths, and Flask reloader
    subprocesses where __file__ may resolve to incorrect paths.
    """
    # Strategy 1: Use STOCKFISH_BASE_DIR env var if set (for deployment)
    env_base = os.environ.get('STOCKFISH_BASE_DIR')
    if env_base and os.path.isdir(env_base):
        return os.path.realpath(env_base)

    # Strategy 2: Try __file__-based resolution
    file_based = os.path.dirname(os.path.realpath(__file__))
    if os.path.isfile(os.path.join(file_based, 'config.py')):
        return file_based

    # Strategy 3: Try CWD-based resolution
    cwd_based = os.getcwd()
    if os.path.isfile(os.path.join(cwd_based, 'config.py')):
        return os.path.realpath(cwd_based)

    # Strategy 4: Try sys.argv[0]-based resolution
    if sys.argv and sys.argv[0]:
        argv_based = os.path.dirname(os.path.realpath(sys.argv[0]))
        if os.path.isfile(os.path.join(argv_based, 'config.py')):
            return argv_based

    # Fallback: return file_based even if it seems wrong
    return file_based


_BASE_DIR = _resolve_base_dir()


def _resolve_stockfish_path(base_dir):
    """Find the Stockfish executable, trying multiple locations."""
    # Check env var first
    env_path = os.environ.get('STOCKFISH_PATH')
    if env_path and os.path.isfile(env_path):
        return env_path

    # Common locations to check
    candidates = [
        os.path.join(base_dir, 'stockfish', 'stockfish', 'stockfish-windows-x86-64-avx2.exe'),
        os.path.join(base_dir, 'stockfish', 'stockfish-windows-x86-64-avx2.exe'),
        os.path.join(base_dir, 'bin', 'stockfish'),
        os.path.join(base_dir, 'bin', 'stockfish.exe'),
    ]

    # On Linux/macOS, also check common paths
    if sys.platform != 'win32':
        candidates.extend([
            '/usr/bin/stockfish',
            '/usr/local/bin/stockfish',
            os.path.join(base_dir, 'stockfish', 'stockfish', 'stockfish-ubuntu-x86-64-avx2'),
            os.path.join(base_dir, 'stockfish', 'stockfish', 'stockfish-arm64'),
            os.path.join(base_dir, 'stockfish', 'stockfish', 'stockfish'),
            os.path.join(base_dir, 'stockfish', 'stockfish'),
        ])

    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate

    # Return the default path even if it doesn't exist (will fall back to mock)
    return candidates[0]


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_recycle': 3600,
        'pool_pre_ping': True,
    }

    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'jwt-dev-secret-key')
    JWT_ACCESS_TOKEN_EXPIRES = 86400

    STOCKFISH_PATH = _resolve_stockfish_path(_BASE_DIR)
    ANALYSIS_DEPTH = int(os.environ.get('ANALYSIS_DEPTH', 20))
    ANALYSIS_TIMEOUT = int(os.environ.get('ANALYSIS_TIMEOUT', 300))
    ANALYSIS_THREADS = int(os.environ.get('ANALYSIS_THREADS', 1))
    ANALYSIS_HASH = int(os.environ.get('ANALYSIS_HASH', 256))

    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', os.path.join(_BASE_DIR, 'uploads'))
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024

    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '*')


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URI',
        'sqlite:///' + os.path.join(_BASE_DIR, 'chessdb.db')
    )


class ProductionConfig(Config):
    DEBUG = False
    # Render/Heroku use DATABASE_URL; also support DATABASE_URI for flexibility
    _database_url = os.environ.get('DATABASE_URL') or os.environ.get('DATABASE_URI')
    if _database_url and _database_url.startswith('postgres'):
        # SQLAlchemy 1.4+ requires postgresql:// instead of postgres://
        SQLALCHEMY_DATABASE_URI = _database_url.replace('postgres://', 'postgresql://', 1)
    elif _database_url:
        SQLALCHEMY_DATABASE_URI = _database_url
    else:
        SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(_BASE_DIR, 'chessdb.db')


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(_BASE_DIR, 'test_chess.db')
    WTF_CSRF_ENABLED = False


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig,
}
