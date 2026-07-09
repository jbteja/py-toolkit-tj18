#!/usr/bin/env python
import argparse
import sys
from inspect import signature

# Try to import and detect version
try:
    from pymodbus.client import ModbusSerialClient
    import pymodbus
    version = pymodbus.__version__
    is_old = version.startswith('1.')
except ImportError:
    print("pymodbus not installed. Run: pip install pymodbus")
    sys.exit(1)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", required=True)
    parser.add_argument("--slave", type=int, default=1)
    parser.add_argument("--baudrate", type=int, default=9600)
    args = parser.parse_args()

    # Create client
    if is_old:
        # pymodbus 1.x: unit goes in constructor
        client = ModbusSerialClient(
            port=args.port,
            baudrate=args.baudrate,
            parity='N',
            stopbits=1,
            bytesize=8,
            timeout=1
        )
    else:
        # pymodbus 3.x: use method='rtu' and slave in read calls
        client = ModbusSerialClient(
            port=args.port,
            baudrate=args.baudrate,
            parity='N',
            stopbits=1,
            bytesize=8,
            timeout=1
        )

    if not client.connect():
        print("Connection failed")
        sys.exit(1)

    print(f"Connected (pymodbus {version})")

    # Read holding register (address 0x00)
    read_signature = signature(client.read_holding_registers)
    if "device_id" in read_signature.parameters:
        result = client.read_holding_registers(0x00, count=1, device_id=args.slave)
    elif "unit" in read_signature.parameters:
        result = client.read_holding_registers(0x00, 1, unit=args.slave)
    else:
        result = client.read_holding_registers(0x00, 1, args.slave)

    if not result.isError():
        print(f"Device address register = {result.registers[0]}")
    else:
        print(f"Error: {result}")

    client.close()

if __name__ == "__main__":
    main()
