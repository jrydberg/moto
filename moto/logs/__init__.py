from __future__ import unicode_literals
from .models import logs_backends
from ..core.models import MockAWS

logs_backend = logs_backends['us-east-1']


def mock_logs(func=None):
    if func:
        return MockAWS(logs_backends)(func)
    else:
        return MockAWS(logs_backends)
