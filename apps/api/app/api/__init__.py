"""
旧版 Flask API 路由模块（过渡期）

graph、report 已迁移到 FastAPI（见 app/routers/）；
simulation 仍为 Flask 蓝图，经 WSGI 中间件挂载到 FastAPI 上，
待迁移完成后整体删除本模块。
"""

from flask import Blueprint

simulation_bp = Blueprint('simulation', __name__)

from . import simulation  # noqa: E402, F401
