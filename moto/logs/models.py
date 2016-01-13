from __future__ import unicode_literals

import json
import base64
import time
import boto.logs
import uuid

from .exceptions import (ResourceNotFoundException,
                         InvalidSequenceTokenException)

from moto.core import BaseBackend


class OutputLogEvent(object):

    def __init__(self, ingestion_time, timestamp, message):
        self.ingestion_time = ingestion_time
        self.timestamp = timestamp
        self.message = message

    def to_json(self):
        return {
            "ingestionTime": self.ingestion_time,
            "timestamp": self.timestamp,
            "message": self.message
        }


class LogGroup(object):

    def __init__(self):
        self.streams = {}


class LogStream(object):

    def __init__(self):
        self.events = []
        self.sequence_token = None

    def get_events(self, limit, next_token, start_from_head,
                   start_time, end_time):
        limit = limit or 100
        if next_token:
            start_time, end_time, start_from_head, index = json.loads(
                base64.b64decode(next_token))
        else:
            if start_from_head:
                index = 0
            else:
                index = len(self.events)

        if not start_from_head:
            start_index = index - limit
            end_index = index
        else:
            start_index = index
            end_index = index + limit
        start_index = max(0, start_index)
        end_index = min(end_index, len(self.events))

        events = self.events[start_index:end_index]

        next_forward_token = base64.b64encode(json.dumps(
            [start_time, end_time, True, end_index]))
        next_backward_token = base64.b64encode(json.dumps(
            [start_time, end_time, False, start_index]))

        return events, next_forward_token, next_backward_token

    def put_events(self, sequence_token, log_events):
        if sequence_token != self.sequence_token:
            raise InvalidSequenceTokenException()

        for log_event in log_events:
            self.events.append(OutputLogEvent(int(time.time() * 1000),
                               log_event['timestamp'],
                               log_event['message']))

        self.sequence_token = str(uuid.uuid4())
        return self.sequence_token


class CloudWatchLogsBackend(BaseBackend):

    def __init__(self):
        self.groups = {}

    def put(self, group, stream, message, timestamp=None):
        if timestamp is None:
            timestamp = int(time.time() * 1000)
        if group not in self.groups:
            self.groups[group] = LogGroup()
        if stream not in self.groups[group].streams:
            self.groups[group].streams[stream] = LogStream()
        return self.put_log_events(
            group, stream,
            self.groups[group].streams[stream].sequence_token,
            [{"message": message, "timestamp": timestamp}])

    def get_group(self, name):
        if name not in self.groups:
            raise ResourceNotFoundException(name)
        return self.groups.get(name)

    def get_stream(self, group_name, stream_name):
        group = self.get_group(group_name)
        return group.streams.get(stream_name) if group else None

    def get_log_events(self, group_name, stream_name, end_time,
                       limit, next_token, start_from_head,
                       start_time):
        stream = self.get_stream(group_name, stream_name)
        if stream is None:
            raise ResourceNotFoundException(stream_name)
        return stream.get_events(limit, next_token,
                                 start_from_head, start_time, end_time)

    def put_log_events(self, group_name, stream_name, sequence_token,
                       log_events):
        stream = self.get_stream(group_name, stream_name)
        if stream is None:
            raise ResourceNotFoundException()
        return stream.put_events(sequence_token, log_events)


logs_backends = {}
for region in boto.logs.regions():
    logs_backends[region.name] = CloudWatchLogsBackend()
