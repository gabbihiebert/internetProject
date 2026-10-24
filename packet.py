"""
Track B: packet format and parsing for the mini internet.

My job: Responsible for the common network's packet format and parsing, 
plus router forwarding behavior: forwarding tables, hop limits, return paths, 
and error handling. 

Goal of packet.py: define one common network packet format that hosts and routers 
can serialize and parse

Packet format:
    src|dst|hop_limit|msg_type|msg_id|payload


"""

from asyncio.log import logger
import logging
from typing import Optional

# Logging setup for packet file
log = logging.getLogger("packet")

# Contraints for packet size and hop limit
MAX_PACKET_SIZE: int = 1200
MAX_HOP_LIMIT: int = 255


class Packet: # Initialization of a network packet object with the given parameters
    def __init__(self, src, dst, hop_limit, msg_type, msg_id, payload):
        self.src = src
        self.dst = dst
        self.hop_limit = hop_limit
        self.msg_type = msg_type
        self.msg_id = msg_id
        self.payload = payload

        # Defines the type for each field
        src: str
        dst: str
        hop_limit: int
        msg_type: str
        msg_id: int
        payload: bytes


def encode(packet: Packet) -> bytes:
    # Builds a header that separates the parameters with the '|' character
    # Combines the header and payload into a single byte sequence
    log.info(f"Encoded packet: {packet}")
    encoded_packet = f"{packet.src}|{packet.dst}|{packet.hop_limit}|{packet.msg_type}|{packet.msg_id}|".encode() + packet.payload
    return encoded_packet


def decode(data: bytes) -> Optional[Packet]: # Returns a Packet object if decoding is successful, None otherwise.
    if not isinstance(data, bytes):
        log.error("Packet data must be bytes")
        return None
    if len(data) > MAX_PACKET_SIZE:
        log.error("Packet exceeds maximum size")
        return None

    # Splits the encoded byte sequence into header and payload parts
    parts = data.split(b'|', 5)
    if len(parts) != 6:
        log.error("Data does not contain a complete packet header")
        return None

    header = parts[:5]
    payload = parts[5]
    log.info(f"Decoded header: {header}, payload length: {len(payload)}")

    # Does the opposite of encode: parses the byte sequence back into a Packet
    try:
        src = header[0].decode()
        dst = header[1].decode()
        hop_limit = int(header[2].decode())
        msg_type = header[3].decode()
        msg_id = int(header[4].decode())
    except (UnicodeDecodeError, ValueError):
        log.error("Packet header contains invalid fields")
        return None

    # Constructs the packet based off the decoded header and payload
    decoded_packet = Packet(src, dst, hop_limit, msg_type, msg_id, payload)
    log.info(f"Decoded packet: {decoded_packet}")

    # Validates the package with the validate function before returning it.
    if not validate(decoded_packet):
        log.error("Packet validation failed")
        return None

    return decoded_packet


def validate(packet: Packet) -> bool: # Returns True if the packet is valid, False otherwise.
    # Type checking for all packet fields 
    if type(packet.src) != str:
        log.error("Invalid packet: src is not a string")
        return False
    if type(packet.dst) != str:
        log.error("Invalid packet: dst is not a string")
        return False
    if type(packet.hop_limit) != int:
        log.error("Invalid packet: hop_limit is not an int")
        return False
    if type(packet.msg_type) != str:
        log.error("Invalid packet: msg_type is not a string")
        return False
    if type(packet.msg_id) != int:
        log.error("Invalid packet: msg_id is not an int")
        return False
    if type(packet.payload) != bytes:
        log.error("Invalid packet: payload is not bytes")
        return False
    
    # Mandatory fields check
    if not packet.src:
        log.error("Invalid packet: src is empty")
        return False
    if not packet.dst:
        log.error("Invalid packet: dst is empty")
        return False
    if not packet.msg_type:
        log.error("Invalid packet: msg_type is empty")
        return False
    # Range and format checks
    if not 1 <= packet.hop_limit <= MAX_HOP_LIMIT:
        log.error("Invalid packet: hop_limit out of range")
        return False
    if packet.msg_id < 0:
        log.error("Invalid packet: msg_id is negative")
        return False

    # Check for illegal '|' character in string fields
    if "|" in packet.src or "|" in packet.dst or "|" in packet.msg_type:
        log.error("Invalid packet: '|' character found in src, dst, or msg_type")
        return False

    # Check if the encoded packet exceeds the maximum allowed size
    if len(encode(packet)) > MAX_PACKET_SIZE:
        log.error("Invalid packet: exceeds maximum packet size")
        return False

    return True
