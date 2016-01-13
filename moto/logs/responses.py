from __future__ import unicode_literals
import json

from moto.core.responses import BaseResponse
from .models import logs_backends


class CloudWatchLogsResponse(BaseResponse):

    def param(self, name, default=None):
        data = json.loads(self.body)
        return data.get(name, default)

    @property
    def _backend(self):
        return logs_backends[self.region]

    def respond(self, data):
        return json.dumps(data, indent=2)

    def get_log_events(self):
        events, forward_token, backward_token = self._backend.get_log_events(
            self.param('logGroupName'),
            self.param('logStreamName'),
            self.param('endTime'),
            self.param('limit'),
            self.param('nextToken'),
            self.param('startFromHead', False),
            self.param('startTime'))
        return self.respond({
            "events": [event.to_json() for event in events],
            "nextBackwardToken": backward_token,
            "nextForwardToken": forward_token
        })

    def put_log_events(self):
        next_sequence_token = self._backend.put_log_events(
            self.param('logGroupName'),
            self.param('logStreamName'),
            self.param('sequenceToken'),
            self.param('logEvents'))
        return self.respond({
            "nextSequenceToken": next_sequence_token
        })
