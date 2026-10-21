# router.py - forwarding router. Delegates all forwarding logic to forwarding.py.

import argparse

from forwarding import ForwardingError, ForwardingTable, prepare_forward
import packet as P
from netnode import open_node


def main():
    # Parse args, build the ForwardingTable, then loop receiving and forwarding.
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--seed", type=int, default=None)
    args = ap.parse_args()

    node = open_node(args.config, args.name, seed=args.seed)

    # Build the ForwardingTable object using Isabelle's class.
    table = ForwardingTable(
        node.cfg.forwarding_table(node.name),
        set(node.cfg.neighbors(node.name)),
    )

    def handle(src_name: str, pkt):
        # Handle one inbound packet: drop, forward, or log an error.
        node.log.info(f"RECV from={src_name} src={pkt.src} dst={pkt.dst} "
                      f"type={pkt.msg_type} msg_id={pkt.msg_id} hop={pkt.hop_limit}")

        # Packet addressed to the router itself is not valid for forwarding.
        if pkt.dst == node.vaddr:
            node.log.warning(f"DROP packet addressed to router msg_id={pkt.msg_id}")
            return

        try:
            next_hop, forwarded = prepare_forward(pkt, table)

        except ForwardingError as e:
            node.log.info(f"DROP reason={e} msg_id={pkt.msg_id} hop={pkt.hop_limit}")
            return

        node.log.info(f"FORWARD src={pkt.src} dst={pkt.dst} next_hop={next_hop} "
                      f"type={pkt.msg_type} msg_id={pkt.msg_id} "
                      f"hop_after_dec={forwarded.hop_limit}")

        node.send_packet(next_hop, forwarded, msg_id=pkt.msg_id)

    try:
        while True:
            got = node.recv_packet(timeout=0.1)

            if got is not None:
                try:
                    handle(*got)

                except Exception as e:
                    node.log.exception(f"handler error: {e}")

    except KeyboardInterrupt:
        node.log.info("shutting down")


if __name__ == "__main__":
    main()