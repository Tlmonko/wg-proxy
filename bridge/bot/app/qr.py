from io import BytesIO

import qrcode


def make_qr_png(payload: str) -> bytes:
    img = qrcode.make(payload)
    buffer = BytesIO()
    # qrcode может вернуть PyPNGImage (без pillow), у которого нет аргумента format.
    img.save(buffer)
    return buffer.getvalue()
