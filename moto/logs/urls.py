from __future__ import unicode_literals
from .responses import CloudWatchLogsResponse

url_bases = [
    "https?://logs.(.+).amazonaws.com",
]

url_paths = {
    '{0}/$': CloudWatchLogsResponse().dispatch,
}
