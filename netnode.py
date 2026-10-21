# netnode.py - UDP socket wrapper, neighbor enforcement, loss/delay injection,
# and the Network adapter that lets reliable.py plug into real UDP sockets.

import heapq
import logging
import random
import socket
import time

import packet as P
from config import load as load_config


MAX_WIRE = 1200


class NetNode:
    # Base UDP node shared by Host and Router; enforces neighbor-only sends.

    def __init__(self, cfg, name: str, run_id: str = None, seed: int = None):
        # Bind a UDP socket, remember config, prepare delay heap and logger.
        self.cfg = cfg
        self.name = name
        self.run_id = run_id or time.strftime("%Y%m%d-%H%M%S")
        self._rng = random.Random(seed)
        self._seed = seed

        d = cfg.device(name)
        self.vaddr = d["virtual_addr"]
        self.kind = d["type"]

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(cfg.endpoint(name))
        self.sock.settimeout(0.1)

        self._delayed = []
        self._seq = 0

        self.log = logging.getLogger(name)
        self.log.setLevel(logging.INFO)

        if not self.log.handlers:
            fmt = logging.Formatter(
                f"%(asctime)s run={self.run_id} dev={name} %(levelname)s %(message)s")
            sh = logging.StreamHandler()
            sh.setFormatter(fmt)
            self.log.addHandler(sh)

        self.log.info(f"started kind={self.kind} vaddr={self.vaddr} "
                      f"endpoint={cfg.endpoint(name)} seed={seed}")

    def send_packet(self, neighbor: str, pkt, msg_id=None) -> bool:
        # Serialize and send a Packet to a configured neighbor with delay/loss applied.
        if neighbor not in self.cfg.neighbors(self.name):
            self.log.error(f"REFUSE send to non-neighbor '{neighbor}'")
            return False

        raw = P.encode(pkt)

        if len(raw) > MAX_WIRE:
            self.log.error(f"REFUSE oversized send len={len(raw)} > {MAX_WIRE}")
            return False

        cond = self.cfg.link_condition(self.name, neighbor)

        if cond["loss"] > 0 and self._rng.random() < cond["loss"]:
            self.log.info(f"DROP injected loss link={self.name}->{neighbor} "
                          f"seed={self._seed} msg_id={pkt.msg_id} type={pkt.msg_type}")
            return True

        if cond["delay_ms"] > 0:
            deliver_at = time.monotonic() + cond["delay_ms"] / 1000.0
            self._seq += 1
            heapq.heappush(self._delayed, (deliver_at, self._seq, neighbor, raw))
            self.log.info(f"SEND(delayed {cond['delay_ms']}ms) -> {neighbor} "
                          f"msg_id={pkt.msg_id} type={pkt.msg_type}")

        else:
            self.sock.sendto(raw, self.cfg.endpoint(neighbor))
            self.log.info(f"SEND -> {neighbor} msg_id={pkt.msg_id} "
                          f"type={pkt.msg_type} len={len(raw)}")

        return True

    def _drain_delayed(self):
        # Send any delayed packets whose delivery time has passed.
        now = time.monotonic()

        while self._delayed and self._delayed[0][0] <= now:
            _, _, neighbor, raw = heapq.heappop(self._delayed)

            try:
                self.sock.sendto(raw, self.cfg.endpoint(neighbor))
                self.log.info(f"SEND(flush) -> {neighbor} len={len(raw)}")

            except OSError as e:
                self.log.error(f"flush send to {neighbor} failed: {e}")

    def recv_packet(self, timeout: float = 0.1):
        # Poll for one valid packet from a configured neighbor; return (src_name, Packet) or None.
        self._drain_delayed()
        self.sock.settimeout(timeout)

        try:
            raw, addr = self.sock.recvfrom(MAX_WIRE + 100)

        except socket.timeout:
            return None

        except OSError as e:
            self.log.error(f"recv error: {e}")
            return None

        src_name = self.cfg.name_for_port(addr[1])

        if src_name is None or src_name not in self.cfg.neighbors(self.name):
            self.log.warning(f"DROP packet from non-neighbor endpoint {addr}")
            return None

        pkt = P.decode(raw)

        if pkt is None:
            self.log.warning(f"DROP malformed packet from {src_name}")
            return None

        return src_name, pkt


class NetworkAdapter:
    # Adapter exposing send(dest, msg_type, msg_id, payload) / recv(timeout) for reliable.py.

    def __init__(self, node: NetNode, dst_vaddr: str):
        # Wrap a NetNode so Gabbi's reliable code can call .send and .recv.
        self.node = node
        self.dst_vaddr = dst_vaddr
        self._inbox = []

    def _first_hop(self, dst_vaddr: str):
        # Look up the neighbor name to reach a destination virtual address.
        tbl = self.node.cfg.forwarding_table(self.node.name)

        return tbl.get(dst_vaddr)

    def send(self, dest_vaddr: str, msg_type: str, msg_id: int, payload: bytes):
        # Build a Packet and ship it toward dest_vaddr through the first-hop neighbor.
        pkt = P.Packet(self.node.vaddr, dest_vaddr, 16, msg_type, msg_id, payload)
        nh = self._first_hop(dest_vaddr)

        if nh is None:
            self.node.log.warning(f"NO ROUTE to {dest_vaddr} msg_id={msg_id}")
            return

        self.node.send_packet(nh, pkt, msg_id=msg_id)

    def recv(self, timeout: float):
        # Return the next inbound Packet addressed to us, or None after timeout.
        deadline = time.monotonic() + timeout

        while True:
            if self._inbox:
                return self._inbox.pop(0)

            remaining = deadline - time.monotonic()

            if remaining <= 0:
                return None

            got = self.node.recv_packet(min(remaining, 0.05))

            if got is None:
                continue

            src_name, pkt = got

            if pkt.dst != self.node.vaddr:
                self.node.log.warning(f"DROP wrong-dest dst={pkt.dst} (I am {self.node.vaddr})")
                continue

            self._inbox.append(pkt)


def open_node(config_path: str, name: str, run_id: str = None, seed: int = None) -> NetNode:
    # Load config and return a bound NetNode for the named device.
    cfg = load_config(config_path)

    return NetNode(cfg, name, run_id=run_id, seed=seed)