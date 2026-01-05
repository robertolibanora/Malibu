from app import create_app
import ssl
import os
import ipaddress
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from datetime import datetime, timedelta

def generate_self_signed_cert():
    """Genera un certificato self-signed se non esiste già"""
    cert_file = "cert.pem"
    key_file = "key.pem"
    
    # Se i file esistono già, li usiamo
    if os.path.exists(cert_file) and os.path.exists(key_file):
        return (cert_file, key_file)
    
    # Genera una chiave privata
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    
    # Crea il certificato
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "IT"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Italia"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, "Roma"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "MalibuApp"),
        x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
    ])
    
    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).public_key(
        private_key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.utcnow()
    ).not_valid_after(
        datetime.utcnow() + timedelta(days=365)
    ).add_extension(
        x509.SubjectAlternativeName([
            x509.DNSName("localhost"),
            x509.DNSName("127.0.0.1"),
            x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
        ]),
        critical=False,
    ).sign(private_key, hashes.SHA256())
    
    # Salva il certificato
    with open(cert_file, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    
    # Salva la chiave privata
    with open(key_file, "wb") as f:
        f.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ))
    
    return (cert_file, key_file)

app = create_app()

if __name__ == "__main__":
    try:
        cert_file, key_file = generate_self_signed_cert()
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert_file, key_file)
        app.run(host="0.0.0.0", port=8123, debug=True, ssl_context=context)
    except Exception as e:
        print(f"Errore nella configurazione SSL: {e}")
        print("Avvio senza HTTPS...")
        app.run(host="0.0.0.0", port=8123, debug=True)