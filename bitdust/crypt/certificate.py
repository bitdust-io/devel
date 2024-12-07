#!/usr/bin/python
# certificate.py
#
# Copyright (C) 2008 Veselin Penev, https://bitdust.io
#
# This file (certificate.py) is part of BitDust Software.
#
# BitDust is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# BitDust Software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with BitDust Software.  If not, see <http://www.gnu.org/licenses/>.
#
# Please contact us if you have any questions at bitdust.io@gmail.com
#
#
#
#
"""
.. module:: certificate.

"""

#------------------------------------------------------------------------------

from __future__ import absolute_import
from __future__ import print_function

#------------------------------------------------------------------------------

_Debug = True
_DebugLevel = 10

#------------------------------------------------------------------------------

import datetime
import ipaddress
import uuid

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives import hashes
from cryptography.x509.oid import NameOID

#------------------------------------------------------------------------------


def generate_private_key(key_size=2048):
    """
    Create a private key
    """
    pkey = rsa.generate_private_key(public_exponent=65537, key_size=key_size, backend=default_backend())
    pkey_pem = pkey.private_bytes(
        encoding=serialization.Encoding.PEM,
        # format=serialization.PrivateFormat.PKCS8,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return pkey, pkey_pem


def load_private_key(pkey_pem):
    """
    Load private key from PEM text
    """
    pkey = serialization.load_pem_private_key(
        data=pkey_pem,
        password=None,
        backend=default_backend(),
    )
    return pkey


def load_certificate(cert_pem):
    """
    Load private key from PEM text
    """
    pub_key = x509.load_pem_x509_certificate(
        data=cert_pem,
        backend=default_backend(),
    )
    return pub_key


def generate_self_signed_cert(hostname, server_key, ip_addresses=None):
    """
    Generates self signed certificate for a hostname, and optional IP addresses.
    """
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, hostname)])
    alt_names = [x509.DNSName(hostname)]
    if ip_addresses:
        for addr in ip_addresses:
            alt_names.append(x509.DNSName(addr))
            alt_names.append(x509.IPAddress(ipaddress.ip_address(addr)))

    ca_crt = x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(server_key.public_key()).serial_number(uuid.uuid4().int, ).not_valid_before(
        datetime.datetime.utcnow()
    ).not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=365*100)).add_extension(
        extension=x509.KeyUsage(digital_signature=True, key_encipherment=True, key_cert_sign=True, crl_sign=True, content_commitment=True, data_encipherment=False, key_agreement=False, encipher_only=False, decipher_only=False),
        critical=False,
    ).add_extension(
        extension=x509.BasicConstraints(ca=True, path_length=0),
        critical=False,
    ).add_extension(
        extension=x509.SubjectKeyIdentifier.from_public_key(server_key.public_key()),
        critical=False,
    ).add_extension(
        extension=x509.AuthorityKeyIdentifier.from_issuer_public_key(server_key.public_key()),
        critical=False,
    ).add_extension(
        extension=x509.SubjectAlternativeName(alt_names),
        critical=False,
    ).sign(
        private_key=server_key,
        algorithm=hashes.SHA256(),
        backend=default_backend(),
    )
    ca_cert_pem = ca_crt.public_bytes(encoding=serialization.Encoding.PEM)

    return ca_cert_pem


def generate_csr_client_cert(hostname, server_ca_cert, server_key, client_key):
    """
    Generate client-side certificate with CSR.
    """
    csr = x509.CertificateSigningRequestBuilder().subject_name(x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, hostname),
    ]), ).add_extension(
        x509.SubjectAlternativeName([
            x509.DNSName(hostname),
        ]),
        critical=False,
    ).sign(client_key, hashes.SHA256(), default_backend())
    crt = x509.CertificateBuilder().subject_name(csr.subject).issuer_name(server_ca_cert.subject).public_key(csr.public_key()).serial_number(uuid.uuid4().int, ).not_valid_before(
        datetime.datetime.utcnow()
    ).not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=365*100)).add_extension(
        extension=x509.KeyUsage(digital_signature=True, key_encipherment=True, content_commitment=True, data_encipherment=False, key_agreement=False, encipher_only=False, decipher_only=False, key_cert_sign=False, crl_sign=False),
        critical=True,
    ).add_extension(
        extension=x509.BasicConstraints(ca=False, path_length=None),
        critical=True,
    ).add_extension(
        extension=x509.AuthorityKeyIdentifier.from_issuer_public_key(server_key.public_key()),
        critical=False,
    ).sign(
        private_key=server_key,
        algorithm=hashes.SHA256(),
        backend=default_backend(),
    )
    crt_pem = crt.public_bytes(serialization.Encoding.PEM)
    return crt_pem
