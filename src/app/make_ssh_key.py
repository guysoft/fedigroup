from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
import os
from .common import ensure_dir

def generate_keys(path):
    # generate private/public key pair
    key = rsa.generate_private_key(backend=default_backend(), public_exponent=65537, key_size=2048)

    # get public key in OpenSSH format
    public_key = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.PKCS1)

    # get private key in PEM container format
    pem = key.private_bytes(encoding=serialization.Encoding.PEM,
                            format=serialization.PrivateFormat.TraditionalOpenSSL,
                            encryption_algorithm=serialization.NoEncryption())

    # decode to printable strings
    private_key_str = pem.decode('utf-8')
    public_key_str = public_key.decode('utf-8')

    ensure_dir(path)

    private_key_path = os.path.join(path, "id_rsa")
    with open(private_key_path, "w") as w:
        w.write(private_key_str)
    os.chmod(private_key_path, 0o600)
    with open(os.path.join(path, "id_rsa.pub"), "w") as w:
        w.write(public_key_str)

    return private_key_str, public_key_str
