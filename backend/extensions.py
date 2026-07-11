"""Application extension instances.

Keeping extensions in one module avoids circular imports and lets the app
factory initialize every integration in a predictable order.
"""

from flask_bcrypt import Bcrypt
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_migrate import Migrate
from flask_socketio import SocketIO
from sqlalchemy import MetaData
from flask_sqlalchemy import SQLAlchemy


NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

db = SQLAlchemy(metadata=MetaData(naming_convention=NAMING_CONVENTION))
migrate = Migrate()
bcrypt = Bcrypt()
jwt = JWTManager()
cors = CORS()
socketio = SocketIO(
    async_mode="eventlet",
    cors_allowed_origins=[],
    logger=False,
    engineio_logger=False,
)
limiter = Limiter(key_func=get_remote_address)
