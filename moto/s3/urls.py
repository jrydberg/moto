from __future__ import unicode_literals
#from .responses import S3ResponseInstance


DNS_COMPATIBLE_BASE_URL = "https?://(?P<bucket_name>[a-zA-Z0-9\-_.]+)\.s3(.*).amazonaws.com"
NON_DNS_COMPATIBLE_BASE_URL= "https?://s3(.*).amazonaws.com"

#url_bases = [
#    "https?://(?P<bucket_name>[a-zA-Z0-9\-_.]*)\.?s3(.*).amazonaws.com"
#]

#url_paths = {
#    '{0}/$': S3ResponseInstance.bucket_response,
#    '{0}/(?P<key_name>.+)': S3ResponseInstance.key_response,
#}
