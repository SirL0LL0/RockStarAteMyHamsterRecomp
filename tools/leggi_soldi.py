#!/usr/bin/env python3
"""leggi_soldi.py - soldi e flag "saldo negativo" nella memoria salvata da un test."""
import sys

m = open(sys.argv[1] if len(sys.argv) > 1 else 'build/memoria_fine.bin', 'rb').read()
cifre = m[0x123CA:0x123D2]
print("soldi a $123CA:", ''.join(str(c) for c in cifre), " saldo negativo ($128BD):", m[0x128BD])
