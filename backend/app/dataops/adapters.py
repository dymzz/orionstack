"""S3 API, Apache Tika and ClamAV adapters. No uploaded filename is trusted."""
import base64
import os
import re
import socket
import struct
from contextlib import contextmanager
from urllib.parse import urlsplit, quote
import httpx
from app.dataops.ports import DependencyUnavailable, AssetRejected


def chunks(data):
    data.seek(0)
    while block := data.read(1024 * 1024): yield block


class S3ObjectStorage:
    def __init__(self, client=None, bucket=None):
        self.bucket = bucket or os.getenv('ORIONSTACK_S3_BUCKET', '')
        if not self.bucket: raise DependencyUnavailable('Object storage is not configured')
        if client is not None: self.client = client; return
        import boto3
        from botocore.config import Config
        endpoint = os.getenv('ORIONSTACK_S3_ENDPOINT') or None
        if endpoint and urlsplit(endpoint).scheme not in ('https', 'http'):
            raise DependencyUnavailable('Invalid object storage endpoint')
        self.client = boto3.client('s3', endpoint_url=endpoint,
            region_name=os.getenv('ORIONSTACK_S3_REGION', 'us-east-1'),
            aws_access_key_id=os.getenv('ORIONSTACK_S3_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('ORIONSTACK_S3_SECRET_ACCESS_KEY'),
            aws_session_token=os.getenv('ORIONSTACK_S3_SESSION_TOKEN'),
            config=Config(signature_version='s3v4', connect_timeout=5, read_timeout=30,
                retries={'max_attempts': 2}, s3={'addressing_style': 'path'}))

    def upload_url(self, key, size):
        try:
            url = self.client.generate_presigned_url('put_object',
                Params={'Bucket': self.bucket, 'Key': key, 'ContentLength': size,
                    'ContentType': 'application/octet-stream'}, ExpiresIn=300)
            return url, {'Content-Type': 'application/octet-stream'}
        except Exception: raise DependencyUnavailable('Object storage signing failed') from None

    @contextmanager
    def open_upload(self, key):
        body = None
        try:
            body = self.client.get_object(Bucket=self.bucket, Key=key)['Body']
            yield body
        except (DependencyUnavailable, AssetRejected): raise
        except Exception: raise DependencyUnavailable('Uploaded object is unavailable') from None
        finally:
            if body is not None: body.close()

    def put_verified(self, key, data, media_type, sha256):
        try:
            data.seek(0)
            result = self.client.put_object(Bucket=self.bucket, Key=key, Body=data,
                ContentType=media_type, ChecksumSHA256=base64.b64encode(bytes.fromhex(sha256)).decode())
            return result.get('VersionId')
        except Exception: raise DependencyUnavailable('Verified object storage failed') from None

    def download_url(self, key, filename, version_id):
        params = {'Bucket': self.bucket, 'Key': key,
            'ResponseContentDisposition': "attachment; filename*=UTF-8''" + quote(filename, safe=''),
            'ResponseContentType': 'application/octet-stream'}
        if version_id: params['VersionId'] = version_id
        try: return self.client.generate_presigned_url('get_object', Params=params, ExpiresIn=60)
        except Exception: raise DependencyUnavailable('Download signing failed') from None


class TikaMediaDetector:
    def __init__(self, endpoint=None, client=None):
        self.endpoint = endpoint or os.getenv('ORIONSTACK_TIKA_URL', '')
        if not self.endpoint: raise DependencyUnavailable('Apache Tika is not configured')
        if urlsplit(self.endpoint).scheme not in ('http', 'https'):
            raise DependencyUnavailable('Invalid Apache Tika endpoint')
        self.client = client

    def detect(self, data):
        # /detect/stream receives actual bytes, never a filename or browser MIME hint.
        try:
            with (self.client or httpx.Client(timeout=30, follow_redirects=False, trust_env=False)) as client:
                with client.stream('PUT', self.endpoint.rstrip('/') + '/detect/stream',
                        content=chunks(data), headers={'Content-Type': 'application/octet-stream', 'Accept': 'text/plain'}) as response:
                    response.raise_for_status()
                    result = b''
                    for block in response.iter_bytes():
                        result += block
                        if len(result) > 256: raise ValueError('Invalid detection response')
                    media = result.decode().strip().lower()
                    if not re.fullmatch(r'[a-z0-9.+-]+/[a-z0-9.+-]+', media): raise ValueError('Invalid MIME')
                    return media
        except Exception: raise DependencyUnavailable('Apache Tika detection failed') from None


class ClamAVScanner:
    def __init__(self, host=None, port=None):
        self.host = host or os.getenv('ORIONSTACK_CLAMAV_HOST', '')
        if not self.host: raise DependencyUnavailable('ClamAV is not configured')
        self.port = port or int(os.getenv('ORIONSTACK_CLAMAV_PORT', '3310'))

    def scan(self, data):
        try:
            with socket.create_connection((self.host, self.port), timeout=30) as sock:
                sock.sendall(b'zINSTREAM\0')
                for block in chunks(data): sock.sendall(struct.pack('!I', len(block)) + block)
                sock.sendall(struct.pack('!I', 0))
                response = b''
                while not response.endswith(b'\0'):
                    block = sock.recv(1024)
                    if not block or len(response) + len(block) > 8192: raise ValueError('Invalid scan reply')
                    response += block
                if response == b'stream: OK\0': return True
                if response.startswith(b'stream: ') and response.endswith(b' FOUND\0'): return False
                raise ValueError('ClamAV scan did not complete')
        except Exception: raise DependencyUnavailable('ClamAV scanning failed') from None
