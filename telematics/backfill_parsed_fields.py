"""Backfill script: parse raw_packet for rows that have never been parsed.

Usage (from the project root):
    uv run python -m telematics.backfill_parsed_fields

The script identifies rows where ``header IS NULL`` (the clearest indicator
that a row was stored before field parsing was introduced) and re-parses
each ``raw_packet`` using the same helpers that live packets use today,
including the new CRC-32 checksum verification.

Rows are fetched in batches of BATCH_SIZE and updated one-by-one inside a
single transaction per batch, so a failure mid-batch leaves the DB in a
consistent state (partial batches are rolled back).
"""

import asyncio
import logging
from pathlib import Path

from telematics.database import close_pool, init_pool
from telematics.service import TelematicsService
from telematics.utils import (
    parse_dp_datetime,
    parse_signed_coord,
    safe_bool,
    safe_float,
    safe_int,
)

logger = logging.getLogger(__name__)

BATCH_SIZE = 500


async def backfill(pool) -> None:
    service = TelematicsService(pool)

    total_updated = 0
    total_skipped = 0
    total_errors = 0

    logger.info("Starting backfill of unparsed telematics_events rows ...")

    while True:
        # Fetch from offset 0 every iteration: successfully updated rows drop
        # out of the WHERE clause (header IS NULL -> not null), so we converge.
        rows = await pool.fetch(
            """
            SELECT id, raw_packet
            FROM   telematics_events
            WHERE  header IS NULL
              AND  raw_packet IS NOT NULL
            ORDER  BY id
            LIMIT  $1
            """,
            BATCH_SIZE,
        )

        if not rows:
            break

        logger.info("Processing batch: rows=%d", len(rows))

        batch_updated = 0
        batch_skipped = 0
        batch_errors = 0

        async with pool.acquire() as conn:
            async with conn.transaction():
                for row in rows:
                    row_id: int = row["id"]
                    raw_packet: str = row["raw_packet"]

                    packet_data = service.validate_ais140_packet(raw_packet)

                    if packet_data is None:
                        # Packet doesn't pass basic validation; leave it alone
                        # so it stops being picked up, write a sentinel header.
                        logger.debug(
                            "Row %d: invalid/unrecognised packet, skipping.", row_id
                        )
                        batch_skipped += 1
                        continue

                    header: str = packet_data["header"]
                    fields: list[str] = packet_data["fields"]
                    checksum_matched: bool | None = packet_data["checksum_matched"]

                    if header == "DP":
                        try:
                            async with conn.transaction():  # savepoint per row
                                await conn.execute(
                                    """
                                    UPDATE telematics_events SET
                                        header                   = $2,
                                        vendor_id                = $3,
                                        firmware_version         = $4,
                                        packet_type              = $5,
                                        alert_id                 = $6,
                                        packet_status            = $7,
                                        imei                     = $8,
                                        vehicle_reg_no           = $9,
                                        gps_fix                  = $10,
                                        gps_datetime             = $11,
                                        latitude                 = $12,
                                        longitude                = $13,
                                        speed                    = $14,
                                        heading                  = $15,
                                        num_satellites           = $16,
                                        altitude                 = $17,
                                        pdop                     = $18,
                                        hdop                     = $19,
                                        operator_name            = $20,
                                        ignition                 = $21,
                                        main_power_status        = $22,
                                        main_input_voltage       = $23,
                                        internal_battery_voltage = $24,
                                        emergency_status         = $25,
                                        tamper_alert             = $26,
                                        gsm_signal_strength      = $27,
                                        mcc                      = $28,
                                        mnc                      = $29,
                                        lac                      = $30,
                                        cell_id                  = $31,
                                        nmr1_lac                 = $32,
                                        nmr1_cell_id             = $33,
                                        nmr1_signal_strength     = $34,
                                        nmr2_lac                 = $35,
                                        nmr2_cell_id             = $36,
                                        nmr2_signal_strength     = $37,
                                        nmr3_lac                 = $38,
                                        nmr3_cell_id             = $39,
                                        nmr3_signal_strength     = $40,
                                        nmr4_lac                 = $41,
                                        nmr4_cell_id             = $42,
                                        nmr4_signal_strength     = $43,
                                        din_status               = $44,
                                        dout_status              = $45,
                                        device_mode              = $46,
                                        distance                 = $47,
                                        adc1                     = $48,
                                        adc2                     = $49,
                                        frame_number             = $50,
                                        ota_command              = $51,
                                        checksum                 = $52,
                                        checksum_matched         = $53
                                    WHERE id = $1
                                    """,
                                    row_id,
                                    header,
                                    fields[1],
                                    fields[2],
                                    fields[3],
                                    safe_int(fields[4]),
                                    fields[5],
                                    fields[6],
                                    fields[7],
                                    safe_bool(fields[8]),
                                    parse_dp_datetime(fields[9], fields[10]),
                                    parse_signed_coord(fields[11], fields[12]),
                                    parse_signed_coord(fields[13], fields[14]),
                                    safe_float(fields[15]),
                                    safe_float(fields[16]),
                                    safe_int(fields[17]),
                                    safe_float(fields[18]),
                                    safe_float(fields[19]),
                                    safe_float(fields[20]),
                                    fields[21],
                                    safe_bool(fields[22]),
                                    safe_bool(fields[23]),
                                    safe_float(fields[24]),
                                    safe_float(fields[25]),
                                    safe_bool(fields[26]),
                                    fields[27],
                                    safe_int(fields[28]),
                                    fields[29],
                                    fields[30],
                                    fields[31],
                                    fields[32],
                                    fields[33],
                                    fields[34],
                                    fields[35],
                                    fields[36],
                                    fields[37],
                                    fields[38],
                                    fields[39],
                                    fields[40],
                                    fields[41],
                                    fields[42],
                                    fields[43],
                                    fields[44],
                                    fields[45],
                                    fields[46],
                                    safe_int(fields[47]),
                                    safe_float(fields[48]),
                                    safe_int(fields[49]),
                                    safe_int(fields[50]),
                                    safe_int(fields[51]),
                                    fields[52] or None,
                                    fields[53] if len(fields) > 53 else None,
                                    checksum_matched,
                                )
                            batch_updated += 1
                        except Exception:
                            logger.exception(
                                "Row %d: UPDATE failed, row skipped.", row_id
                            )
                            batch_errors += 1

                    else:
                        # Non-DP packet — write at least the header so the row
                        # won't be picked up again on future backfill runs.
                        try:
                            async with conn.transaction():  # savepoint per row
                                await conn.execute(
                                    "UPDATE telematics_events SET header = $2 WHERE id = $1",
                                    row_id,
                                    header,
                                )
                            batch_updated += 1
                        except Exception:
                            logger.exception(
                                "Row %d: header-only UPDATE failed.", row_id
                            )
                            batch_errors += 1

        total_updated += batch_updated
        total_skipped += batch_skipped
        total_errors += batch_errors

        logger.info(
            "Batch done — updated=%d  skipped=%d  errors=%d  |  "
            "running total: updated=%d  skipped=%d  errors=%d",
            batch_updated, batch_skipped, batch_errors,
            total_updated, total_skipped, total_errors,
        )

        # If every row in the batch was skipped (no header written, no WHERE
        # clause change), we'd loop forever. Break out to avoid that.
        if batch_updated == 0 and batch_errors == 0:
            logger.warning(
                "No rows were updated in this batch (all skipped). "
                "Remaining skipped rows cannot be parsed; stopping."
            )
            break

    logger.info(
        "Backfill complete. updated=%d  skipped=%d  errors=%d",
        total_updated,
        total_skipped,
        total_errors,
    )


async def _main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    pool = await init_pool()
    try:
        await backfill(pool)
    finally:
        await close_pool()

    # Self-destruct: remove this script now that the backfill is done.
    script_path = Path(__file__).resolve()
    try:
        script_path.unlink()
        logger.info("Script deleted: %s", script_path)
    except OSError:
        logger.warning("Could not delete script file: %s", script_path, exc_info=True)


if __name__ == "__main__":
    asyncio.run(_main())
