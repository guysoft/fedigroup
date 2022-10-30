from datetime import datetime
import json
import base64
from urllib.parse import urlparse

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric import utils as hazutils
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from time import gmtime, strftime
import requests


def get_sha_256(msg: str):
    """Returns a SHA256 hash of the given string
    """
    digest = hashes.Hash(hashes.SHA256(), backend=default_backend())
    digest.update(msg)
    return digest.finalize()

def message_content_digest(message_body_json_str: str,
                           digest_algorithm: str) -> str:
    """Returns the digest for the message body
    """
    msg = message_body_json_str.encode('utf-8')
    hash_result = get_sha_256(msg)
    return base64.b64encode(hash_result).decode('utf-8')

def sign_post_headers(message_body_json_str, date_str, host, path, preshared_key_id, key_path):
    """Returns a raw signature string that can be plugged into a header and
    used to verify the authenticity of an HTTP transmission.
    """
    # domain = get_full_domain(domain, port)
    digest_algorithm = "rsa-sha256"

    if not date_str:
        date_str = strftime("%a, %d %b %Y %H:%M:%S %Z", gmtime())

    key_data = None
    with open(key_path, 'rb') as fh:
        key_data=fh.read()


    key_id = preshared_key_id
    if not message_body_json_str:
        headers = {
            '(request-target)': f'get {path}',
            'host': host,
            'date': date_str,
            'accept': "application/activity+json"
        }
    else:
        body_digest = \
            message_content_digest(message_body_json_str, digest_algorithm)
        digest_prefix = 'SHA-256'
        headers = {
            '(request-target)': f'post {path}',
            'host': host,
            'date': date_str,
            'digest': f'{digest_prefix}={body_digest}',
            'content-type': 'application/activity+json',
        }
    key = load_pem_private_key(key_data,
                            None, backend=default_backend())
    
    # build a digest for signing
    signed_header_keys = headers.keys()
    signed_header_text = ''
    for header_key in signed_header_keys:
        signed_header_text += f'{header_key}: {headers[header_key]}\n'
    # strip the trailing linefeed
    signed_header_text = signed_header_text.rstrip('\n')
    # signed_header_text.encode('ascii') matches
    header_digest = get_sha_256(signed_header_text.encode('ascii'))
    # print('header_digest2: ' + str(header_digest))

    # Sign the digest
    raw_signature = key.sign(header_digest,
                             padding.PKCS1v15(),
                             hazutils.Prehashed(hashes.SHA256()))
    signature = base64.b64encode(raw_signature).decode('ascii')

    # Put it into a valid HTTP signature format
    algorithm="rsa-sha256"
    signature_dict = {
        'keyId': key_id,
        'algorithm': algorithm,
        'headers': ' '.join(signed_header_keys),
        'signature': signature
    }
    signature_header = ','.join(
        [f'{k}="{v}"' for k, v in signature_dict.items()])
    a = digest_prefix + "=" + body_digest
    return signature_header, a


def send_signed(url, activity, preshared_key_id, key_path):
    parsed = urlparse(url)
    domain = parsed.netloc.split(".")[-2:]
    host = parsed.netloc

    now = datetime.utcnow()
    formatted_now = now.strftime("%a, %d %b %Y %H:%M:%S GMT")
    signed_string = (
            f"(request-target): post /inbox\nhost: {host}\ndate: {formatted_now}"
        )


    body = json.dumps(activity)

    sig, digest = sign_post_headers(body, formatted_now, host, parsed.path, preshared_key_id, key_path)

    header = (
        f'keyId="{preshared_key_id}",headers="(request-target) host date",'
        f'signature="' + sig + '"'
    )

    r = requests.post(url,
        data=body,
        headers={
            "Host": host,
            "Date": formatted_now,
            "Signature": sig,
            "digest": digest,
            "Content-Type": "application/activity+json",
        },
    )

    return r.content