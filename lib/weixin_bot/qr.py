from __future__ import annotations

import qrcode


def print_qr_to_console(data: str) -> None:
    qr = qrcode.QRCode(border=1)
    qr.add_data(data)
    qr.make(fit=True)
    # Avoid Unicode block chars for Windows GBK terminals.
    matrix = qr.get_matrix()
    for row in matrix:
        line = "".join("##" if cell else "  " for cell in row)
        print(line)

