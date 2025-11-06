# app/utils/qr.py
import base64, io, secrets, string
import qrcode

ALPHABET = string.ascii_uppercase + string.digits

def generate_short_code(length=10) -> str:
    # 8-12 alfanumerico con semplice checksum su base36
    core = ''.join(secrets.choice(ALPHABET) for _ in range(length-1))
    checksum = base36_checksum(core)
    return core + checksum

def base36_checksum(s: str) -> str:
    n = sum(ord(c) for c in s) % 36
    return ALPHABET[n]

def qr_data_url(text: str) -> str:
    img = qrcode.make(text)  # richiede `pip install qrcode[pil]`
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
    return f"data:image/png;base64,{b64}"