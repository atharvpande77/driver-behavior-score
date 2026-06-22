import asyncio
import random
import time
import asyncpg
from telematics.logging_utils import get_logger, log_event
from telematics.constants import DB_TIMEOUT_SECONDS
from telematics.utils import (
    compute_checksum_matched,
    get_min_fields_for_header,
    parse_dp_datetime,
    parse_signed_coord,
    safe_bool,
    safe_float,
    safe_int,
)

logger = get_logger(__name__)


def log_failed_packet(raw_packet: str, reason: str, **kwargs) -> None:
    # Sample rate of 10% for failures
    if random.random() < 0.1:
        # Truncate packet to 100 chars
        truncated_packet = raw_packet[:100] + "..." if len(raw_packet) > 100 else raw_packet
        log_event(
            logger,
            "WARNING",
            "telematics.packet.failed_sample",
            raw_packet=truncated_packet,
            reason=reason,
            **kwargs
        )


class TelematicsService:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def _execute_with_retry(self, query: str, *values, max_retries: int = 3, initial_delay: float = 0.5) -> None:
        delay = initial_delay
        for attempt in range(max_retries):
            try:
                async with asyncio.timeout(DB_TIMEOUT_SECONDS):
                    await self.pool.execute(query, *values)
                    return
            except (asyncpg.IntegrityConstraintViolationError, asyncpg.DataError) as e:
                logger.error("DB integrity/data error (not retrying): %s", e)
                raise
            except (asyncpg.PostgresError, OSError, TimeoutError, asyncio.TimeoutError) as e:
                if attempt == max_retries - 1:
                    logger.error("DB transient error on final attempt: %s", e)
                    raise
                logger.warning("DB transient error: %s. Retrying in %.2f seconds...", e, delay)
                await asyncio.sleep(delay)
                delay = min(delay * 2, 5.0)

    async def _fetchrow_with_retry(self, query: str, *values, max_retries: int = 3, initial_delay: float = 0.5) -> asyncpg.Record | None:
        delay = initial_delay
        for attempt in range(max_retries):
            try:
                async with asyncio.timeout(DB_TIMEOUT_SECONDS):
                    return await self.pool.fetchrow(query, *values)
            except (asyncpg.IntegrityConstraintViolationError, asyncpg.DataError) as e:
                logger.error("DB integrity/data error (not retrying): %s", e)
                raise
            except (asyncpg.PostgresError, OSError, TimeoutError, asyncio.TimeoutError) as e:
                if attempt == max_retries - 1:
                    logger.error("DB transient error on final attempt: %s", e)
                    raise
                logger.warning("DB transient error: %s. Retrying in %.2f seconds...", e, delay)
                await asyncio.sleep(delay)
                delay = min(delay * 2, 5.0)

    def validate_ais140_packet(self, raw_packet: str) -> dict | None:
        if (len(raw_packet) < 40) or (not raw_packet.startswith('$')) or (not raw_packet.endswith('*')):
            return None

        fields = raw_packet[1:-1].split(',')
        header = fields[0]

        min_fields = get_min_fields_for_header(header)
        if not min_fields or len(fields) < min_fields:
            return None

        received_checksum = fields[53] if header == 'DP' and len(fields) > 53 else None
        checksum_matched = compute_checksum_matched(raw_packet, received_checksum)

        return {
            "header": header,
            "fields": fields,
            "raw_packet": raw_packet,
            "checksum_matched": checksum_matched,
        }

    async def get_vehicle_number_from_device_imei(self, device_imei: str) -> str | None:
        if not device_imei or len(device_imei) != 15:
            return None

        row = await self._fetchrow_with_retry(
            "SELECT vehicle_reg_no FROM telematics_devices WHERE imei = $1 AND active = true",
            device_imei
        )
        return row["vehicle_reg_no"] if row else None

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
    ) -> None:
        if header == 'DP':
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

        await self._execute_with_retry(query, *values)

        if header == 'DP':
            await self._execute_with_retry(
                """
                UPDATE telematics_devices
                SET last_seen_at = $1, last_source_ip = $2
                WHERE imei = $3
                """,
                dp_params['gps_datetime'],
                source_ip,
                fields[6],
            )

    async def process_packet(
        self,
        packet: str,
        *,
        source_ip: str | None = None,
        source_port: int | None = None,
    ) -> None:
        start_time = time.time()
        raw_packet = packet.strip()

        packet_data = self.validate_ais140_packet(raw_packet)
        if packet_data is None:
            log_event(
                logger,
                "WARNING",
                "telematics.packet.invalid",
                source_ip=source_ip,
                reason="validation_failed"
            )
            log_failed_packet(raw_packet, "validation_failed", source_ip=source_ip)
            return

        header, fields = packet_data['header'], packet_data['fields']
        imei = fields[6] if len(fields) > 6 else None

        db_start = time.time()
        try:
            vehicle_number = await self.get_vehicle_number_from_device_imei(imei)
        except Exception as e:
            db_ms = (time.time() - db_start) * 1000.0
            processing_ms = (time.time() - start_time) * 1000.0
            log_event(
                logger,
                "ERROR",
                "telematics.database.error",
                imei=imei,
                source_ip=source_ip,
                packet_header=header,
                reason="resolve_imei_failed",
                database_ms=round(db_ms, 2),
                processing_ms=round(processing_ms, 2)
            )
            return

        if not vehicle_number:
            db_ms = (time.time() - db_start) * 1000.0
            processing_ms = (time.time() - start_time) * 1000.0
            log_event(
                logger,
                "WARNING",
                "telematics.device.unknown",
                imei=imei,
                source_ip=source_ip,
                packet_header=header,
                reason="imei_not_registered",
                database_ms=round(db_ms, 2),
                processing_ms=round(processing_ms, 2)
            )
            return

        try:
            await self.store_data_packet(
                packet_data['raw_packet'],
                fields=fields,
                header=header,
                vehicle_reg_no=vehicle_number,
                checksum_matched=packet_data['checksum_matched'],
                source_ip=source_ip,
                source_port=source_port,
            )
            db_ms = (time.time() - db_start) * 1000.0
            processing_ms = (time.time() - start_time) * 1000.0

            frame_num = safe_int(fields[51]) if len(fields) > 51 else None
            log_event(
                logger,
                "INFO",
                "telematics.packet.success",
                imei=imei,
                source_ip=source_ip,
                packet_header=header,
                frame_number=frame_num,
                database_ms=round(db_ms, 2),
                processing_ms=round(processing_ms, 2)
            )
        except Exception as e:
            db_ms = (time.time() - db_start) * 1000.0
            processing_ms = (time.time() - start_time) * 1000.0
            log_event(
                logger,
                "ERROR",
                "telematics.database.error",
                imei=imei,
                source_ip=source_ip,
                packet_header=header,
                reason="store_packet_failed",
                database_ms=round(db_ms, 2),
                processing_ms=round(processing_ms, 2)
            )
            log_failed_packet(raw_packet, "store_failed", imei=imei, source_ip=source_ip)