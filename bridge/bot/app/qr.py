from io import BytesIO

import qrcode


def make_qr_png(payload: str) -> bytes:
    img = qrcode.make(payload)
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    return buffer.getvalue()
