from __future__ import unicode_literals
from .models import ec2containerservice_backends
from ..core.models import MockAWS

ec2containerservice_backend = ec2containerservice_backends['us-east-1']


def mock_ec2containerservice(func=None):
    if func:
        return MockAWS(ec2containerservice_backends)(func)
    else:
        return MockAWS(ec2containerservice_backends)
