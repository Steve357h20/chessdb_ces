from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from config import config

db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["2000 per day", "500 per hour"],
    storage_uri="memory://",
)


def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    db.init_app(app)
    migrate.init_app(app, db)
    cors_origins = app.config.get('CORS_ORIGINS', '*')
    CORS(app, resources={
        r"/api/*": {"origins": cors_origins},
        r"/admin/*": {"origins": cors_origins},
        r"/apidocs/*": {"origins": cors_origins},
        r"/flasgger/*": {"origins": cors_origins},
        r"/apispec*": {"origins": cors_origins},
        r"/": {"origins": cors_origins},
    })
    jwt.init_app(app)
    limiter.init_app(app)

    from app.routes import register_blueprints, register_error_handlers
    register_blueprints(app)
    register_error_handlers(app)

    from app.swagger_config import setup_swagger
    setup_swagger(app)

    from app.admin import setup_admin
    setup_admin(app)

    # 注册 API 流量监控中间件 + 管理后台 API
    from app.traffic import init_traffic_middleware, admin_api_bp, submit_bp
    app.register_blueprint(admin_api_bp)
    app.register_blueprint(submit_bp)
    init_traffic_middleware(app)

    with app.app_context():
        from app import models
        db.create_all()
        from app.services.puzzle_library import init_system_puzzles
        init_system_puzzles()

    return app
