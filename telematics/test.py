from __future__ import annotations

import zlib


packet = "$DP,BB100V,4GC6508,DT,16,L,865510083289001,NA,1,04062026,105811,21.118496,N,79.042183,E,0.0,117.8,32,318,0.9,0.4,AIRTEL,0,1,12.83,4.18,0,C,25,404,90,10FA,1907,8806,10FA,24,6008,10FA,23,6003,10FA,22,1903,10FA,21,0000,00,3,465.7,0,0,001963,(),99E05B54*"


def calculate_checksum(packet: str):
    body = packet[1:packet.rfind("*")]
    payload, transmitted_crc = body.rsplit(",", 1)

    calculated = zlib.crc32(payload.encode("ascii")) & 0xFFFFFFFF

    return f"{calculated:08X}", transmitted_crc


calc, received = calculate_checksum(packet)
print(calc, received, calc == received)