"""
Track B: forwarding behavior for the mini internet.

My job: Responsible for the common network's packet format and parsing, 
plus router forwarding behavior: forwarding tables, hop limits, return paths, 
and error handling. 

Goal of forwarding.py: define functions and classes that manage packet forwarding 
in the network.

Forwarding behavior: 
    - Maintain forwarding tables
    - Decrement hop limits
    - Determine return paths
    - Handle errors
"""

import logging
from packet import Packet

# Logging set up for forwarding file
log = logging.getLogger("forwarding")


class ForwardingError(Exception):
    # Raised for general forwarding-related errors
    pass


class ForwardingTable: # Manages the forwarding table and neighbor relationships for a router.
    def __init__(self, routes: dict[str, str], neighbors: set[str]):
        # Store the routing table and the set of configured neighbors.
        self.routes = routes
        self.neighbors = neighbors

        for dest, next_hop in self.routes.items():
            if next_hop not in self.neighbors:
                log.error(f"Next hop {next_hop} for destination {dest} is not a configured neighbor.")
                raise ForwardingError(f"Next hop {next_hop} for destination {dest} is not a configured neighbor.")


    # Returns the next hop for the given destination, raising an error if it cannot be determined.
    def next_hop(self, destination: str) -> str:
        # Look up the next hop for the given destination in the routing table.
        if destination not in self.routes:
            log.error(f"No forwarding entry for destination {destination}")
            raise ForwardingError(f"No forwarding entry for destination {destination}")

        # Retrieve the next hop for the destination and validate it against the configured neighbors.
        next_hop = self.routes[destination]
        if next_hop not in self.neighbors:
            log.error(f"Next hop {next_hop} for destination {destination} is not a configured neighbor.")
            raise ForwardingError(f"Next hop {next_hop} for destination {destination} is not a configured neighbor.")

        log.info(f"Next hop for destination {destination} is {next_hop}")
        return next_hop


def prepare_forward(packet: Packet, table: ForwardingTable) -> tuple[str, Packet]: 
    # Prepare a packet for forwarding by decrementing its hop limit and determining the next hop.
    # A packet with hop limit 1 cannot be forwarded.
    if packet.hop_limit <= 1:
        log.error(f"Hop limit exceeded for destination {packet.dst}")
        raise ForwardingError(f"Hop limit exceeded for destination {packet.dst}")

    # Find the configured neighbor for this packet's destination.
    next_hop = table.next_hop(packet.dst)

    # Make a forwarded copy with the hop limit reduced by one.
    forwarded_packet = Packet(
        packet.src,
        packet.dst,
        packet.hop_limit - 1,
        packet.msg_type,
        packet.msg_id,
        packet.payload,
    )

    log.info(f"Prepared packet for forwarding to next hop {next_hop}: {forwarded_packet}")
    return next_hop, forwarded_packet