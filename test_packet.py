""" 
Track B: Testing Packet format

My job: Responsible for the common network's packet format and parsing, 
plus router forwarding behavior: forwarding tables, hop limits, return paths, 
and error handling. 

Goal of test_packet.py: Test the packet.py implementation and error handling

"""

import unittest

from packet import MAX_PACKET_SIZE, Packet, decode, encode, validate


class TestPacket(unittest.TestCase): # Testing the Packet class and its functions
    def setUp(self):
        # A normal packet from one host to another.
        self.packet = Packet("Host1", "Host2", 8, "DATA", 1, b"hello")

    def test_encode_and_decode(self): # Testing encoding and decoding functions 
        decoded = decode(encode(self.packet))

        # Make sure that decodeing the encoded packet equals the original packet
        self.assertIsNotNone(decoded)
        self.assertEqual(decoded.src, self.packet.src)
        self.assertEqual(decoded.dst, self.packet.dst)
        self.assertEqual(decoded.hop_limit, self.packet.hop_limit)
        self.assertEqual(decoded.msg_type, self.packet.msg_type)
        self.assertEqual(decoded.msg_id, self.packet.msg_id)
        self.assertEqual(decoded.payload, self.packet.payload)

    def test_payload_can_contain_separator(self): # Testing that the payload syntax is correctly handled
        packet = Packet("Host1", "Host2", 8, "DATA", 1, b"hello|there")

        decoded = decode(encode(packet))
        # Make sure that decoding the encoded packet maintains the payload correctly
        self.assertIsNotNone(decoded)
        self.assertEqual(decoded.payload, b"hello|there")

    def test_decode_rejects_non_bytes(self):
        # Make sure that decode rejects the type thats not bytes 
        self.assertIsNone(decode("not bytes"))

    def test_decode_rejects_incomplete_header(self):
        # Make sure that decode rejects packets with an incomplete header
        self.assertIsNone(decode(b"Host1|Host2|8|DATA"))

    def test_decode_rejects_invalid_number(self):
        # Make sure that decodes rejects packets with an invalid number in the header
        self.assertIsNone(decode(b"Host1|Host2|bad|DATA|1|hello"))

    def test_decode_rejects_oversized_packet(self):
        # Make sure that decode rejects packets that exceed max packet size
        self.assertIsNone(decode(b"x" * (MAX_PACKET_SIZE + 1)))

    def test_validate_rejects_invalid_hop_limit(self):
        packet = Packet("Host1", "Host2", 0, "DATA", 1, b"hello")

        # Make sure that validate rejects packets with an invalid hop limit
        self.assertFalse(validate(packet))

    def test_validate_rejects_negative_message_id(self):
        packet = Packet("Host1", "Host2", 8, "DATA", -1, b"hello")

        # Make sure that validate rejects packets with a negative message ID
        self.assertFalse(validate(packet))

    def test_validate_rejects_wrong_payload_type(self):
        packet = Packet("Host1", "Host2", 8, "DATA", 1, "hello")

        # Make sure that validate rejects packets with the wrong payload type
        self.assertFalse(validate(packet))

    def test_validate_rejects_packet_over_size_limit(self):
        packet = Packet("Host1", "Host2", 8, "DATA", 1, b"x" * MAX_PACKET_SIZE)

        # Make sure that validate rejects packets that exceed the max packet size
        self.assertFalse(validate(packet))


if __name__ == "__main__":
    unittest.main()