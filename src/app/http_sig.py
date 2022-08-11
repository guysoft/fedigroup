# Code to sign, handle and validate https
# Some code taken from https://gitlab.com/bashrc2/epicyon/-/blob/main/httpsig.py
import requests
import json
from urllib.parse import urlparse
import base64
from datetime import datetime
import traceback

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric import utils as hazutils
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from time import gmtime, strftime
import asyncio

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

def sign_post_headers(message_body_json_str, date_str, host, path, key_path, preshared_key_id):
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

def send_signed(url, activity, key_id, preshared_key_id):
    parsed = urlparse(url)
    domain = parsed.netloc.split(".")[-2:]
    host = ".".join(domain)    

    now = datetime.utcnow()
    formatted_now = now.strftime("%a, %d %b %Y %H:%M:%S GMT")

    body = json.dumps(activity)
    sig, digest = sign_post_headers(body, formatted_now, host, parsed.path, key_id, preshared_key_id)

    # await asyncio.sleep(5)

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




def _verify_recent_signature(signed_date_str: str) -> bool:
    """Checks whether the given time taken from the header is within
    12 hours of the current time
    """
    curr_date = datetime.utcnow()
    date_format = "%a, %d %b %Y %H:%M:%S %Z"
    signed_date = datetime.strptime(signed_date_str, date_format)
    time_diff_sec = (curr_date - signed_date).seconds
    # 12 hours tollerance
    if time_diff_sec > 43200:
        print('WARN: Header signed too long ago: ' + signed_date_str)
        print(str(time_diff_sec / (60 * 60)) + ' hours')
        return False
    if time_diff_sec < 0:
        print('WARN: Header signed in the future! ' + signed_date_str)
        print(str(time_diff_sec / (60 * 60)) + ' hours')
        return False
    return True


def verify_post_headers(http_prefix: str,
                        public_key_pem: str, headers: dict,
                        path: str, get_method: bool,
                        message_body_digest: str,
                        message_body_json_str: str, debug: bool,
                        no_recency_check: bool = False) -> bool:
    """Returns true or false depending on if the key that we plugged in here
    validates against the headers, method, and path.
    public_key_pem - the public key from an rsa key pair
    headers - should be a dictionary of request headers
    path - the relative url that was requested from this site
    get_method - GET or POST
    message_body_json_str - the received request body (used for digest)
    """

    if get_method:
        method = 'GET'
    else:
        method = 'POST'

    if debug:
        print('DEBUG: verify_post_headers ' + method)
        print('verify_post_headers public_key_pem: ' + str(public_key_pem))
        print('verify_post_headers headers: ' + str(headers))
        print('verify_post_headers message_body_json_str: ' +
              str(message_body_json_str))

    pubkey = load_pem_public_key(public_key_pem.encode('utf-8'),
                                 backend=default_backend())
    # pubkey = public_key_pem
    # Build a dictionary of the signature values
    if headers.get('Signature-Input') or headers.get('signature-input'):
        if headers.get('Signature-Input'):
            signature_header = headers['Signature-Input']
        else:
            signature_header = headers['signature-input']
        field_sep2 = ','
        # split the signature input into separate fields
        signature_dict = {
            k.strip(): v.strip()
            for k, v in [i.split('=', 1) for i in signature_header.split(';')]
        }
        request_target_key = None
        request_target_str = None
        for key_str, value_str in signature_dict.items():
            if value_str.startswith('('):
                request_target_key = key_str
                request_target_str = value_str[1:-1]
            elif value_str.startswith('"'):
                signature_dict[key_str] = value_str[1:-1]
        if not request_target_key:
            return False
        signature_dict[request_target_key] = request_target_str
    else:
        request_target_key = 'headers'
        signature_header = headers['signature']
        field_sep2 = ' '
        # split the signature input into separate fields
        signature_dict = {
            k: v[1:-1]
            for k, v in [i.split('=', 1) for i in signature_header.split(',')]
        }

    if debug:
        print('signature_dict: ' + str(signature_dict))

    # Unpack the signed headers and set values based on current headers and
    # body (if a digest was included)
    signed_header_list = []
    algorithm = 'rsa-sha256'
    digest_algorithm = 'rsa-sha256'
    for signed_header in signature_dict[request_target_key].split(field_sep2):
        signed_header = signed_header.strip()
        if debug:
            print('DEBUG: verify_post_headers signed_header=' + signed_header)
        if signed_header == '(request-target)':
            # original Mastodon http signature
            append_str = f'(request-target): {method.lower()} {path}'
            signed_header_list.append(append_str)
        elif '@request-target' in signed_header:
            # https://tools.ietf.org/html/
            # draft-ietf-httpbis-message-signatures
            append_str = f'@request-target: {method.lower()} {path}'
            signed_header_list.append(append_str)
        elif '@created' in signed_header:
            if signature_dict.get('created'):
                created_str = str(signature_dict['created'])
                append_str = f'@created: {created_str}'
                signed_header_list.append(append_str)
        elif '@expires' in signed_header:
            if signature_dict.get('expires'):
                expires_str = str(signature_dict['expires'])
                append_str = f'@expires: {expires_str}'
                signed_header_list.append(append_str)
        elif '@method' in signed_header:
            append_str = f'@expires: {method}'
            signed_header_list.append(append_str)
        elif '@scheme' in signed_header:
            signed_header_list.append('@scheme: http')
        elif '@authority' in signed_header:
            authority_str = None
            if signature_dict.get('authority'):
                authority_str = str(signature_dict['authority'])
            elif signature_dict.get('Authority'):
                authority_str = str(signature_dict['Authority'])
            if authority_str:
                append_str = f'@authority: {authority_str}'
                signed_header_list.append(append_str)
        elif signed_header == 'algorithm':
            if headers.get(signed_header):
                algorithm = headers[signed_header]
                if debug:
                    print('http signature algorithm: ' + algorithm)
        elif signed_header == 'digest':
            if message_body_digest:
                body_digest = message_body_digest
            else:
                body_digest = \
                    message_content_digest(message_body_json_str,
                                           digest_algorithm)
            signed_header_list.append(f'digest: {body_digest}')
        elif signed_header == 'content-length':
            if headers.get(signed_header):
                append_str = f'content-length: {headers[signed_header]}'
                signed_header_list.append(append_str)
            elif headers.get('Content-Length'):
                content_length = headers['Content-Length']
                signed_header_list.append(f'content-length: {content_length}')
            elif headers.get('Content-length'):
                content_length = headers['Content-length']
                append_str = f'content-length: {content_length}'
                signed_header_list.append(append_str)
            else:
                if debug:
                    print('DEBUG: verify_post_headers ' + signed_header +
                          ' not found in ' + str(headers))
        else:
            if headers.get(signed_header):
                if signed_header == 'date' and not no_recency_check:
                    if not _verify_recent_signature(headers[signed_header]):
                        if debug:
                            print('DEBUG: ' +
                                  'verify_post_headers date is not recent ' +
                                  headers[signed_header])
                        return False
                signed_header_list.append(
                    f'{signed_header}: {headers[signed_header]}')
            else:
                if '-' in signed_header:
                    # capitalise with dashes
                    # my-header becomes My-Header
                    header_parts = signed_header.split('-')
                    signed_header_cap = None
                    for part in header_parts:
                        if signed_header_cap:
                            signed_header_cap += '-' + part.capitalize()
                        else:
                            signed_header_cap = part.capitalize()
                else:
                    # header becomes Header
                    signed_header_cap = signed_header.capitalize()

                if debug:
                    print('signed_header_cap: ' + signed_header_cap)

                # if this is the date header then check it is recent
                if signed_header_cap == 'Date':
                    signed_hdr_cap = headers[signed_header_cap]
                    if not _verify_recent_signature(signed_hdr_cap):
                        if debug:
                            print('DEBUG: ' +
                                  'verify_post_headers date is not recent ' +
                                  headers[signed_header])
                        return False

                # add the capitalised header
                if headers.get(signed_header_cap):
                    signed_header_list.append(
                        f'{signed_header}: {headers[signed_header_cap]}')
                elif '-' in signed_header:
                    # my-header becomes My-header
                    signed_header_cap = signed_header.capitalize()
                    if headers.get(signed_header_cap):
                        signed_header_list.append(
                            f'{signed_header}: {headers[signed_header_cap]}')

    # Now we have our header data digest
    signed_header_text = '\n'.join(signed_header_list)
    if debug:
        print('\nverify_post_headers signed_header_text:\n' +
              signed_header_text + '\nEND\n')

    # Get the signature, verify with public key, return result
    if (headers.get('Signature-Input') and headers.get('Signature')) or \
       (headers.get('signature-input') and headers.get('signature')):
        # https://tools.ietf.org/html/
        # draft-ietf-httpbis-message-signatures
        if headers.get('Signature'):
            headers_sig = headers['Signature']
        else:
            headers_sig = headers['signature']
        # remove sig1=:
        if request_target_key + '=:' in headers_sig:
            headers_sig = headers_sig.split(request_target_key + '=:')[1]
            headers_sig = headers_sig[:len(headers_sig)-1]
        signature = base64.b64decode(headers_sig)
    else:
        # Original Mastodon signature
        headers_sig = signature_dict['signature']
        signature = base64.b64decode(headers_sig)
    if debug:
        print('signature: ' + algorithm + ' ' + headers_sig)

    # log unusual signing algorithms
    if signature_dict.get('alg'):
        print('http signature algorithm: ' + signature_dict['alg'])

    # If extra signing algorithms need to be added then do it here
    if not signature_dict.get('alg'):
        alg = hazutils.Prehashed(hashes.SHA256())
    elif (signature_dict['alg'] == 'rsa-sha256' or
          signature_dict['alg'] == 'rsa-v1_5-sha256' or
          signature_dict['alg'] == 'hs2019'):
        alg = hazutils.Prehashed(hashes.SHA256())
    elif (signature_dict['alg'] == 'rsa-sha512' or
          signature_dict['alg'] == 'rsa-pss-sha512'):
        alg = hazutils.Prehashed(hashes.SHA512())
    else:
        alg = hazutils.Prehashed(hashes.SHA256())

    if digest_algorithm == 'rsa-sha256':
        header_digest = get_sha_256(signed_header_text.encode('ascii'))
    elif digest_algorithm == 'rsa-sha512':
        header_digest = get_sha_512(signed_header_text.encode('ascii'))
    else:
        print('Unknown http digest algorithm: ' + digest_algorithm)
        header_digest = ''
    padding_str = padding.PKCS1v15()

    try:
        # print(alg)
        # # MODDEDs
        # alg = hazutils.Prehashed(hashes.SHA256())
        # header_digest = get_sha_256(signed_header_text.encode('ascii'))
        # print(signed_header_text)
        
        pubkey.verify(signature, header_digest, padding_str, alg)
        return True
    except BaseException as e:        
        if debug:
            print("Failed to validate signiture, error: ")
            traceback.print_exc()
            print(e)
        
            print('EX: verify_post_headers pkcs1_15 verify failure')
    return False
