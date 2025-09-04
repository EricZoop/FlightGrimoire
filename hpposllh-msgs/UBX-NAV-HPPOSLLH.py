import struct
import sys

def parse_ubx_nav_hpposllh(data):
    """
    Parse UBX NAV-HPPOSLLH message (0x01 0x14)
    Returns parsed position data or None if invalid.
    """
    if len(data) < 36:  # Minimum payload size for NAV-HPPOSLLH
        print(f"  Payload too short: {len(data)} bytes, need 36")
        return None
    
    try:
        # Show raw payload in hex for debugging
        print(f"  Raw payload ({len(data)} bytes): {' '.join(f'{b:02X}' for b in data[:36])}")
        
        # CORRECTED: This format string now correctly describes all 36 bytes.
        version, flags, iTOW, lon, lat, height, hMSL, \
        lonHp, latHp, heightHp, hMSLHp, hAcc, vAcc = \
        struct.unpack('<B2xBI4i4b2I', data[:36])

        # Breakdown of the format string '<B2xBI4i4b2I':
        # <        - Little-endian byte order
        # B        - version (1 byte)
        # 2x       - Skip 2 reserved bytes
        # B        - flags (1 byte)
        # I        - iTOW (4 bytes)
        # 4i       - lon, lat, height, hMSL (4 x 4 = 16 bytes)
        # 4b       - lonHp, latHp, heightHp, hMSLHp (4 x 1 = 4 bytes)
        # 2I       - hAcc, vAcc (2 x 4 = 8 bytes)
        # TOTAL:   - 1 + 2 + 1 + 4 + 16 + 4 + 8 = 36 bytes

        # --- The rest of the function logic is the same ---

        # Calculate high-precision coordinates
        lon_hp = (lon * 1e-7) + (lonHp * 1e-9)
        lat_hp = (lat * 1e-7) + (latHp * 1e-9)
        height_hp = (height * 1e-3) + (heightHp * 1e-4)  # in meters
        hMSL_hp = (hMSL * 1e-3) + (hMSLHp * 1e-4)      # in meters

        # Correctly scale accuracy from 0.1mm units to meters
        hAcc_m = hAcc * 1e-4  # in meters
        vAcc_m = vAcc * 1e-4  # in meters
        
        # Check the invalid LLH flag (bit 0 of the flags byte)
        invalid_llh = (flags & 0x01) == 1
        if invalid_llh:
            print("  Warning: 'invalidLlh' flag is set. Position is not valid.")

        return {
            'iTOW': iTOW,
            'version': version,
            'flags': flags,
            'invalid_llh': invalid_llh,
            'longitude': lon_hp,
            'latitude': lat_hp,
            'height_ellipsoid': height_hp,
            'height_msl': hMSL_hp,
            'horizontal_accuracy': hAcc_m,
            'vertical_accuracy': vAcc_m
        }
    except struct.error as e:
        print(f"  Struct unpack error: {e}")
        return None
    except Exception as e:
        print(f"  Parse error: {e}")
        return None

def find_ubx_messages(data):
    """
    Find all UBX messages in binary data.
    Returns list of (class, id, payload) tuples.
    """
    messages = []
    i = 0
    
    print(f"Scanning {len(data)} bytes for UBX messages...")
    
    while i < len(data) - 8:  # Need at least 8 bytes for header + length + checksum
        # Look for UBX sync chars (0xB5 0x62)
        if data[i] == 0xB5 and data[i+1] == 0x62:
            print(f"Found UBX sync at byte {i}: {data[i]:02X} {data[i+1]:02X}")
            try:
                msg_class = data[i+2]
                msg_id = data[i+3]
                length = struct.unpack('<H', data[i+4:i+6])[0]
                
                print(f"  Class: 0x{msg_class:02X}, ID: 0x{msg_id:02X}, Length: {length}")
                
                # Check if we have enough data for the complete message
                if i + 8 + length <= len(data):
                    payload = data[i+6:i+6+length]
                    
                    # Verify checksum
                    ck_a_rcvd = data[i+6+length]
                    ck_b_rcvd = data[i+6+length+1]
                    
                    # Calculate expected checksum
                    calc_ck_a = calc_ck_b = 0
                    for byte in data[i+2:i+6+length]:
                        calc_ck_a = (calc_ck_a + byte) & 0xFF
                        calc_ck_b = (calc_ck_b + calc_ck_a) & 0xFF
                    
                    print(f"  Checksum: Rcvd {ck_a_rcvd:02X} {ck_b_rcvd:02X}, Calc {calc_ck_a:02X} {calc_ck_b:02X}")
                    
                    if ck_a_rcvd == calc_ck_a and ck_b_rcvd == calc_ck_b:
                        print("  ✓ Valid UBX message found!")
                        messages.append((msg_class, msg_id, payload))
                        i += 8 + length  # Skip to next potential message
                    else:
                        print("  ✗ Checksum mismatch")
                        i += 1  # Invalid checksum, try next byte
                else:
                    print("  ✗ Not enough data for complete message")
                    i += 1  # Not enough data for complete message
            except (struct.error, IndexError) as e:
                print(f"  ✗ Error parsing header: {e}")
                i += 1
        else:
            i += 1
    
    return messages

def process_file(filename):
    """
    Process a binary file and extract UBX NAV-HPPOSLLH messages.
    """
    try:
        with open(filename, 'rb') as f:
            data = f.read()
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found")
        return
    except Exception as e:
        print(f"Error reading file: {e}")
        return
    
    print(f"Processing file: {filename}")
    print(f"File size: {len(data)} bytes")
    print("-" * 50)
    
    # Find all UBX messages
    messages = find_ubx_messages(data)
    
    nav_hpposllh_count = 0
    other_ubx_count = 0
    
    print("\n--- PARSING MESSAGES ---")
    for msg_class, msg_id, payload in messages:
        if msg_class == 0x01 and msg_id == 0x14:  # NAV-HPPOSLLH
            nav_hpposllh_count += 1
            print(f"\nParsing NAV-HPPOSLLH Message #{nav_hpposllh_count}:")
            result = parse_ubx_nav_hpposllh(payload)
            
            if result:
                print(f"\n--- Parsed Data for NAV-HPPOSLLH #{nav_hpposllh_count} ---")
                print(f"  Time of Week: {result['iTOW']} ms")
                print(f"  Latitude:          {result['latitude']:.9f}°")
                print(f"  Longitude:         {result['longitude']:.9f}°")
                print(f"  Height (ellipsoid):{result['height_ellipsoid']: .4f} m")
                print(f"  Height (MSL):      {result['height_msl']: .4f} m")
                print(f"  Horizontal Acc:    {result['horizontal_accuracy']: .4f} m")
                print(f"  Vertical Acc:      {result['vertical_accuracy']: .4f} m")
                print(f"  Position Valid:    {not result['invalid_llh']}")
                print("-" * 50)
            else:
                print(f"NAV-HPPOSLLH Message #{nav_hpposllh_count}: Parse error")
                print("-" * 50)
        else:
            other_ubx_count += 1
    
    print(f"\nSummary:")
    print(f"  NAV-HPPOSLLH messages found: {nav_hpposllh_count}")
    print(f"  Other UBX messages found:    {other_ubx_count}")
    print(f"  Total UBX messages:          {len(messages)}")

# --- Main Execution ---
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python your_script_name.py <filename>")
        # Example for direct execution in an IDE
        # Replace "path/to/your/file.bin" with an actual file path
        # process_file("path/to/your/file.bin") 
    else:
        process_file(sys.argv[1])