from slowapi import Limiter

from src.core.utils import get_ipaddr


# Module-level Limiter singleton. key_func extracts the real client IP from
# X-Forwarded-For (set by Apache mod_proxy) with a fallback to the direct
# connection host for local development.
#
# Registered on app.state.limiter in src/main.py so slowapi's internal
# exception handler can locate it at runtime.
#
# Rate limits are read from AppSettings (AUTH_*_RATE_LIMIT) and applied via
# @limiter.limit(...) decorators on the individual auth routes in router.py.
limiter = Limiter(key_func=get_ipaddr)
