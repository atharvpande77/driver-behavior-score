from telematics.utils import (
    compute_checksum_matched,
    get_min_fields_for_header,
    parse_dp_datetime,
    parse_signed_coord,
    safe_bool,
    safe_float,
    safe_int,
)


class TelematicsService:
    def __init__(self, pool):
        self.pool = pool


    def validate_ais140_packet(self, raw_packet: str) -> dict | None:
        if (len(raw_packet) < 40) or (not raw_packet.startswith('$')) or (not raw_packet.endswith('*')):
            return None

        fields = raw_packet[1:-1].split(',')

        header = fields[0]

        min_fields = get_min_fields_for_header(header)

        if not min_fields or len(fields) < min_fields:
            return None

        # Extract the received checksum (last field for DP packets) and verify
        received_checksum = fields[53] if header == 'DP' and len(fields) > 53 else None
        checksum_matched = compute_checksum_matched(raw_packet, received_checksum)

        return {
            "header": header,
            "fields": fields,
            "raw_packet": raw_packet,
            "checksum_matched": checksum_matched,
        }


    def get_vehicle_number_from_device_imei(self, device_imei: str) -> str | None:
        if not device_imei or len(device_imei) != 15:
            return None

        REGISTERED_VEHICLES = {
            "865510083289001": "MH31CS1928"
        }

        return REGISTERED_VEHICLES.get(device_imei)


    async def store_data_packet(
        self,
        raw_packet: str,
        *,
        fields: list[str],
        header: str,
        vehicle_reg_no: str,
        checksum_matched: bool | None = None,
        source_ip: str | None = None,
        source_port: int | None = None,
    ):
        if header == 'DP':
            # fields[12] = lat dir (N/S), fields[14] = lon dir (E/W)
            dp_params = {
                'header':                   header,
                'vendor_id':                fields[1],
                'firmware_version':         fields[2],
                'packet_type':              fields[3],
                'alert_id':                 safe_int(fields[4]),
                'packet_status':            fields[5],
                'imei':                     fields[6],
                'vehicle_reg_no':           vehicle_reg_no,
                'gps_fix':                  safe_bool(fields[8]),
                'gps_datetime':             parse_dp_datetime(fields[9], fields[10]),
                'latitude':                 parse_signed_coord(fields[11], fields[12]),
                'longitude':                parse_signed_coord(fields[13], fields[14]),
                'speed':                    safe_float(fields[15]),
                'heading':                  safe_float(fields[16]),
                'num_satellites':           safe_int(fields[17]),
                'altitude':                 safe_float(fields[18]),
                'pdop':                     safe_float(fields[19]),
                'hdop':                     safe_float(fields[20]),
                'operator_name':            fields[21],
                'ignition':                 safe_bool(fields[22]),
                'main_power_status':        safe_bool(fields[23]),
                'main_input_voltage':       safe_float(fields[24]),
                'internal_battery_voltage': safe_float(fields[25]),
                'emergency_status':         safe_bool(fields[26]),
                'tamper_alert':             fields[27],
                'gsm_signal_strength':      safe_int(fields[28]),
                'mcc':                      fields[29],
                'mnc':                      fields[30],
                'lac':                      fields[31],
                'cell_id':                  fields[32],
                'nmr1_lac':                 fields[33],
                'nmr1_cell_id':             fields[34],
                'nmr1_signal_strength':     fields[35],
                'nmr2_lac':                 fields[36],
                'nmr2_cell_id':             fields[37],
                'nmr2_signal_strength':     fields[38],
                'nmr3_lac':                 fields[39],
                'nmr3_cell_id':             fields[40],
                'nmr3_signal_strength':     fields[41],
                'nmr4_lac':                 fields[42],
                'nmr4_cell_id':             fields[43],
                'nmr4_signal_strength':     fields[44],
                'din_status':               fields[45],
                'dout_status':              fields[46],
                'device_mode':              safe_int(fields[47]),
                'distance':                 safe_float(fields[48]),
                'adc1':                     safe_int(fields[49]),
                'adc2':                     safe_int(fields[50]),
                'frame_number':             safe_int(fields[51]),
                'ota_command':              fields[52] or None,
                'checksum':                 fields[53] if len(fields) > 53 else None,
                'checksum_matched':          checksum_matched,
            }

            cols = ', '.join(dp_params.keys()) + ', raw_packet, source_ip, source_port'
            placeholders = ', '.join(f'${i}' for i in range(1, len(dp_params) + 4))
            query = f"INSERT INTO telematics_events ({cols}) VALUES ({placeholders})"
            values = list(dp_params.values()) + [raw_packet, source_ip, source_port]

        else:
            query = """
                INSERT INTO telematics_events (header, vehicle_reg_no, raw_packet, source_ip, source_port)
                VALUES ($1, $2, $3, $4, $5)
            """
            values = [header, vehicle_reg_no, raw_packet, source_ip, source_port]

        await self.pool.execute(query, *values)


    async def process_packet(
        self,
        packet: bytes,
        *,
        source_ip: str | None = None,
        source_port: int | None = None,
    ) -> None:
        raw_packet = packet.decode("utf-8", errors="replace").replace("\x00", "\\x00")
        raw_packet = raw_packet.strip()

        packet_data = self.validate_ais140_packet(raw_packet)
        if packet_data is None:
            return

        header, fields = packet_data['header'], packet_data['fields']

        vehicle_number = self.get_vehicle_number_from_device_imei(fields[6])

        if not vehicle_number:
            return

        await self.store_data_packet(
            packet_data['raw_packet'],
            fields=fields,
            header=header,
            vehicle_reg_no=vehicle_number,
            checksum_matched=packet_data['checksum_matched'],
            source_ip=source_ip,
            source_port=source_port,
        )