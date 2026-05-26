import sys

input_file  = "ql_ble_peripheral_beacon.bin"
output_file = "data.bin"
offset      = 122880

if len(sys.argv) != 2:
    print("Usage: python script.py <hex_address>")
    sys.exit(1)

hex_address   = sys.argv[1]
address_bytes = bytes.fromhex(hex_address)

with open(input_file, 'rb') as f:
    data = f.read()

with open(output_file, 'wb') as f:
    f.write(data)

with open(output_file, 'r+b') as f:
    f.seek(offset)
    f.write(address_bytes)

print(f"Address : {' '.join(f'{b:02X}' for b in address_bytes)}")
print(f"Written : {len(address_bytes)} byte(s) at offset {offset}")
print("Done.")
