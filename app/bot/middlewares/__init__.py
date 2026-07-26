"""Bot middlewares."""

from app.bot.middlewares.auth import AuthorizationMiddleware

__all__ = ("AuthorizationMiddleware",)
