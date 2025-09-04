import struct
import sys
import csv
from datetime import datetime, timedelta, timezone

# --- Time Conversion Helper ---

# We need a fixed reference for the start of the week to calculate the timestamp.
# GPS week starts on Sunday. This finds the date of the most recent Sunday at 00:00:00 UTC.
TODAY_UTC = datetime.now(timezone.utc)
# weekday() is Monday=0, Sunday=6. GPS week starts Sunday.
DAYS_SINCE_SUNDAY = (TODAY_UTC.weekday() + 1) % 7
START_OF_GPS_WEEK = datetime.combine(
    TODAY_UTC.date() - timedelta(days=DAYS_SINCE_SUNDAY),
    datetime.min.time(),
    tzinfo=timezone.utc
)

def itow_to_datetime_str(itow_ms: int) -> str:
    """
    Converts GPS iTOW (ms) to a formatted datetime string.
    Assumes the iTOW is from the current GPS week.
    """
    # Calculate the full timestamp by adding the milliseconds of the week to the start of the week
    timestamp = START_OF_GPS_WEEK + timedelta(milliseconds=itow_ms)
    # Format the timestamp into 'yyyy-MM-dd HH:mm:ss.SSS'
    return timestamp.strftime('%Y-%m-%d %H:%M:%S') + f".{timestamp.microsecond // 1000:03d}"

# --- UBX Parsing Functions ---

def parse_ubx_nav_hpposllh(data: bytes):
    """
    Silently parses a UBX NAV-HPPOSLLH message payload.
    Returns a dictionary with parsed data or None if invalid.
    """
    if len(data) < 36:
        return None
    
    try:
        # Unpack the 36-byte payload into variables
        version, flags, iTOW, lon, lat, height, hMSL, \
        lonHp, latHp, heightHp, hMSLHp, hAcc, vAcc = \
        struct.unpack('<B2xBI4i4b2I', data)

        # Calculate final high-precision values
        lon_hp = (lon * 1e-7) + (lonHp * 1e-9)
        lat_hp = (lat * 1e-7) + (latHp * 1e-9)
        hMSL_hp = (hMSL * 1e-3) + (hMSLHp * 1e-4)

        # Check the 'invalid LLH' flag (bit 0)
        is_valid = (flags & 0x01) == 0

        if not is_valid:
            return None # Ignore invalid position messages

        return {
            'iTOW': iTOW,
            'latitude': lat_hp,
            'longitude': lon_hp,
            'height_msl': hMSL_hp,
        }
    except struct.error:
        return None

def find_ubx_messages(data: bytes) -> list:
    """
    Finds all valid UBX messages in a stream of bytes.
    Returns a list of (class, id, payload) tuples.
    """
    messages = []
    i = 0
    data_len = len(data)
    
    while i < data_len - 8:
        # Look for UBX sync characters (0xB5 0x62)
        if data[i] == 0xB5 and data[i+1] == 0x62:
            try:
                # Unpack header to get class, ID, and payload length
                msg_class, msg_id, length = struct.unpack('<BBH', data[i+2:i+6])
                
                # Check if the full message is in the buffer
                if i + 8 + length > data_len:
                    i += 1
                    continue
                
                payload = data[i+6:i+6+length]
                
                # Verify checksum
                ck_a_rcvd, ck_b_rcvd = data[i+6+length], data[i+7+length]
                
                calc_ck_a = calc_ck_b = 0
                for byte in data[i+2:i+6+length]:
                    calc_ck_a = (calc_ck_a + byte) & 0xFF
                    calc_ck_b = (calc_ck_b + calc_ck_a) & 0xFF
                
                if ck_a_rcvd == calc_ck_a and ck_b_rcvd == calc_ck_b:
                    messages.append((msg_class, msg_id, payload))
                    i += 8 + length  # Skip to the end of the current message
                else:
                    i += 1 # Checksum failed, advance one byte
            except struct.error:
                i += 1
        else:
            i += 1
    
    return messages

# --- Main File Processing and CSV Conversion ---

def process_file_to_csv(input_filename: str, output_filename: str):
    """
    Reads a binary file, finds all UBX NAV-HPPOSLLH messages,
    and writes the parsed data to a CSV file.
    """
    try:
        with open(input_filename, 'rb') as f_in:
            binary_data = f_in.read()
    except FileNotFoundError:
        print(f"Error: Input file not found at '{input_filename}'")
        return
    except Exception as e:
        print(f"Error reading file: {e}")
        return

    # Find all valid UBX messages in the data
    all_messages = find_ubx_messages(binary_data)
    
    # Filter for only the NAV-HPPOSLLH messages we care about
    nav_hpposllh_payloads = [
        payload for msg_class, msg_id, payload in all_messages
        if msg_class == 0x01 and msg_id == 0x14
    ]

    if not nav_hpposllh_payloads:
        print("No valid UBX NAV-HPPOSLLH messages found in the file.")
        return

    # Write the parsed data to the output CSV file
    try:
        with open(output_filename, 'w', newline='') as f_out:
            writer = csv.writer(f_out)
            
            # Write the header row
            writer.writerow(['Time', 'latitude', 'longitude', 'height_msl'])
            
            # Parse each message and write a row to the CSV
            count = 0
            for payload in nav_hpposllh_payloads:
                parsed_data = parse_ubx_nav_hpposllh(payload)
                if parsed_data:
                    # Convert iTOW to the required time format
                    time_str = itow_to_datetime_str(parsed_data['iTOW'])
                    
                    writer.writerow([
                        time_str,
                        f"{parsed_data['latitude']:.9f}",
                        f"{parsed_data['longitude']:.9f}",
                        f"{parsed_data['height_msl']:.4f}",
                    ])
                    count += 1
            print(f"Successfully processed and wrote {count} records to '{output_filename}'")

    except IOError as e:
        print(f"Error writing to CSV file: {e}")

# --- Script Execution ---

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python your_script_name.py <input_binary_file> [output_csv_file]")
        print("Example: python your_script_name.py data.bin output.csv")
    else:
        input_file = sys.argv[1]
        # Use 'output.csv' as the default output filename if not provided
        output_file = sys.argv[2] if len(sys.argv) > 2 else "output.csv"
        process_file_to_csv(input_file, output_file)