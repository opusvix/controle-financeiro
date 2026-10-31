"""Dinheiro em centavos inteiros e formatação brasileira."""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal


def para_centavos(valor: str | int | float | Decimal) -> int:
    """'1.234,56' | '8,98' | 8.98 | Decimal('8.98') -> centavos (int)."""
    if isinstance(valor, int):
        return valor * 100
    if isinstance(valor, str):
        texto = valor.strip().replace("R$", "").replace(" ", "")
        if "," in texto:
            texto = texto.replace(".", "").replace(",", ".")
        valor = Decimal(texto)
    else:
        valor = Decimal(str(valor))
    return int((valor * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def formatar(centavos: int) -> str:
    """898 -> 'R$ 8,98'; -123456 -> '-R$ 1.234,56'."""
    sinal = "-" if centavos < 0 else ""
    reais, cent = divmod(abs(centavos), 100)
    milhar = f"{reais:,}".replace(",", ".")
    return f"{sinal}R$ {milhar},{cent:02d}"
