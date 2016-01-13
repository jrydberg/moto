from __future__ import unicode_literals
import json
from werkzeug.exceptions import HTTPException


class ClientError(HTTPException):

    def __init__(self, code, message):
        super(ClientError, self).__init__()
        data = {
            "__type": code,
            "message": message,
            "type": "Client"
        }
        self.description = json.dumps(data)


class CloudWatchLogsClientError(ClientError):
    code = 400


class InvalidParameterException(CloudWatchLogsClientError):
    def __init__(self, parameter):
        super(InvalidParameterException, self).__init__(
            "InvalidParameter", parameter)


class ResourceNotFoundException(CloudWatchLogsClientError):
    def __init__(self, resource):
        super(ResourceNotFoundException, self).__init__(
            "ResourceNotFound", resource)


class InvalidSequenceTokenException(CloudWatchLogsClientError):
    def __init__(self, token):
        super(InvalidSequenceTokenException, self).__init__(
            "InvalidSequenceToken", token)
