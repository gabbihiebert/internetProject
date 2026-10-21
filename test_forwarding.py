"""
Track B: Testing Forwarding behavior

My job: Responsible for the common network's packet format and parsing, 
plus router forwarding behavior: forwarding tables, hop limits, return paths, 
and error handling. 

Goal of test_forwarding.py: Test the forwarding.py implementation and error handling

"""

import unittest

from forwarding import ForwardingError, ForwardingTable, prepare_forward
from packet import Packet


class TestForwarding(unittest.TestCase):
    def setUp(self):
        # The router can reach Host2 through RouterB.
        self.table = ForwardingTable(
            {"Host2": "RouterB"},
            {"RouterB"},
        )
        self.packet = Packet("Host1", "Host2", 8, "DATA", 1, b"hello")

    def test_next_hop(self):
        # Make sure that the next hop for a destination is correct 
        self.assertEqual(self.table.next_hop("Host2"), "RouterB")

    def test_unknown_destination(self):
        # Make sure that the forwarding table raises errors for unknown next hop destinations
        with self.assertRaises(ForwardingError):
            self.table.next_hop("UnknownHost")

    def test_next_hop_must_be_neighbor(self):
        # Make sure that the next hop is a neighbor of the original router
        with self.assertRaises(ForwardingError):
            ForwardingTable({"Host2": "RouterX"}, {"RouterB"})

    def test_forward_decreases_hop_limit(self):
        next_hop, forwarded = prepare_forward(self.packet, self.table)

        # Make sure that forwarding packet decreases hop limit by 1
        self.assertEqual(next_hop, "RouterB")
        # Make sure that the original packet's hop limit remains unchanged
        self.assertEqual(forwarded.hop_limit, 7)
        # Make sure that the original packet's hop limit is not affected by forwarding
        self.assertEqual(self.packet.hop_limit, 8)

    def test_forward_fails_when_hop_limit_is_one(self):
        packet = Packet("Host1", "Host2", 1, "DATA", 1, b"hello")

        # Make sure that forwarding error is raised when hop limit is 1
        with self.assertRaises(ForwardingError):
            prepare_forward(packet, self.table)

    def test_forward_fails_without_a_route(self):
        packet = Packet("Host1", "UnknownHost", 8, "DATA", 1, b"hello")

        # Make sure that forwarding error is raised when there is no route to the destination
        with self.assertRaises(ForwardingError):
            prepare_forward(packet, self.table)


if __name__ == "__main__":
    unittest.main()