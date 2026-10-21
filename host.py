# host.py - end host. Probe/echo (best-effort) OR reliable transfer via Gabbi's code.

import argparse
import time

import packet as P
from netnode import NetworkAdapter, open_node


MSG_PROBE = "PROBE"
MSG_ECHO  = "ECHO"


def echo_responder(node):
    # Return a handler that answers PROBE packets with an ECHO carrying same msg_id/payload.
    def handle(src_name, pkt):
        # Log the inbound packet; if it is a PROBE for us, send back an ECHO.
        node.log.info(f"RECV from={src_name} src={pkt.src} dst={pkt.dst} "
                      f"type={pkt.msg_type} msg_id={pkt.msg_id} hop={pkt.hop_limit}")

        if pkt.dst != node.vaddr:
            node.log.warning(f"DROP wrong-dest dst={pkt.dst}")
            return

        if pkt.msg_type == MSG_PROBE:
            reply = P.Packet(node.vaddr, pkt.src, 16, MSG_ECHO, pkt.msg_id, pkt.payload)
            nh = node.cfg.forwarding_table(node.name).get(pkt.src)

            if nh is None:
                node.log.warning(f"NO ROUTE back to {pkt.src}")
                return

            node.send_packet(nh, reply, msg_id=pkt.msg_id)

    return handle


def run_probes(node, dst_vaddr: str, count: int, interval: float, timeout: float):
    # Send `count` probes to dst_vaddr and report matching-echo RTTs or timeouts.
    pending = {}
    start = time.time()
    msg_id_base = int(start) % 1_000_000_000

    for i in range(count):
        msg_id = msg_id_base + i
        payload = f"probe-{i}".encode()
        pending[msg_id] = {"sent": time.monotonic(), "done": False, "rtt": None}

        pkt = P.Packet(node.vaddr, dst_vaddr, 16, MSG_PROBE, msg_id, payload)
        nh = node.cfg.forwarding_table(node.name).get(dst_vaddr)

        if nh is None:
            node.log.warning(f"NO ROUTE to {dst_vaddr}")
            return

        node.send_packet(nh, pkt, msg_id=msg_id)

        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            got = node.recv_packet(timeout=min(0.05, deadline - time.monotonic()))

            if got is None:
                continue

            _, rpkt = got

            if (rpkt.msg_type == MSG_ECHO and rpkt.msg_id in pending
                    and rpkt.src == dst_vaddr and not pending[rpkt.msg_id]["done"]):
                pending[rpkt.msg_id]["done"] = True
                pending[rpkt.msg_id]["rtt"] = (time.monotonic() - pending[rpkt.msg_id]["sent"]) * 1000
                node.log.info(f"ECHO-MATCH msg_id={rpkt.msg_id} rtt_ms={pending[rpkt.msg_id]['rtt']:.1f}")
                break

        if not pending[msg_id]["done"]:
            node.log.info(f"TIMEOUT msg_id={msg_id} dst={dst_vaddr}")

        time.sleep(interval)

    received = sum(1 for p in pending.values() if p["done"])
    node.log.info(f"SUMMARY sent={count} received={received} "
                  f"lost={count - received} success_rate={received / count:.3f}")


def run_reliable(node, dst_vaddr: str, count: int):
    # Send `count` numbered messages via Gabbi's ReliableSender using our adapter.
    from reliable import ReliableSender

    network = NetworkAdapter(node, dst_vaddr)
    sender = ReliableSender(network, timeout=0.5, max_retries=5)
    messages = [f"msg-{i}".encode() for i in range(count)]
    run_id = int(time.time()) % (2**32)

    result = sender.send_all(dst_vaddr, run_id, messages)

    node.log.info(f"RELIABLE result success={result.success} "
                  f"acked={result.delivered_acked}/{result.total_msgs} "
                  f"retx={result.retransmissions} elapsed={result.elapsed:.2f}s "
                  f"reason={result.reason}")

def run_reliable_receiver(node):
    # I wait for numbered messages and keep each one once, in order
    from reliable import ReliableReceiver
    network = NetworkAdapter(node, None)
    receiver = ReliableReceiver(network, linger=2.0, idle_timeout=30.0)
    receiver.run()
    node.log.info(f"RELIABLE receiver done complete={receiver.complete} "
                  f"delivered={len(receiver.delivered)} duplicates={receiver.duplicates}")

def main():
    # Entry point: choose echo / probe / reliable mode from CLI args.
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--mode", choices=["echo", "probe", "reliable", "reliable-recv"], required=True)
    ap.add_argument("--dst", help="destination virtual address (probe/reliable)")
    ap.add_argument("--count", type=int, default=5)
    ap.add_argument("--interval", type=float, default=1.0)
    ap.add_argument("--timeout", type=float, default=3.0)
    args = ap.parse_args()

    node = open_node(args.config, args.name, seed=args.seed)

    if args.mode == "echo":
        try:
            while True:
                got = node.recv_packet(timeout=0.2)

                if got is not None:
                    try:
                        echo_responder(node)(*got)

                    except Exception as e:
                        node.log.exception(f"handler error: {e}")

        except KeyboardInterrupt:
            pass

    elif args.mode == "probe":
        run_probes(node, args.dst, args.count, args.interval, args.timeout)

    elif args.mode == "reliable":
        run_reliable(node, args.dst, args.count)

    elif args.mode == "reliable-recv":
        run_reliable_receiver(node)

if __name__ == "__main__":
    main()