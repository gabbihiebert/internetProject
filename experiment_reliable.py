"""
Comparison experiment for Track B: best effort vs stop and wait.

I send the same 20 messages both ways, at 0% and 5% random loss, 3 runs
each, and print what happened. Loss is applied to BOTH directions of the one
link between sender and receiver (so ACKs can get lost too).

NOTE: this is a practice run on a pretend (in memory) network, so I can check
my numbers and my table before I run on the real mini internet.

To run it: python experiment_reliable.py

"""

# modules for waiting on messages, random loss, running two things at once, and averages
import logging
import queue
import random
import statistics
import threading
import time

from reliable import (ReliableSender, ReliableReceiver, BestEffortSender, BestEffortReceiver, Packet)

# settings I keep the SAME for every run
MESSAGES = [f"msg-{i}".encode() for i in range(20)] # the same 20 messages every time
LOSS_LEVELS = [0.0, 0.05] # 0% loss and 5% loss
RUNS = 3 # how many times I repeat each condition
DELAY = 0.01 # seconds a message takes to cross the link
MIN_GAP = 0.02 # my speed limit: at least 20 ms between sends (both senders)
ACK_TIMEOUT = 0.1 # stop and wait resends after waiting this long
OBSERVE_TIME = 1.0 # best effort receiver listens this long, then stops

# hide the sender's "timeout" warnings so my table stays easy to read
logging.getLogger("reliable").setLevel(logging.ERROR)


class LossyNet:
    # one end of my pretend link. It loses messages at random.
    def __init__(self, name, inbox, outbox, loss, rng):
        self.name = name # who I am, like "A" or "B"
        self.inbox = inbox # where messages for me wait
        self.outbox = outbox # where I put messages for the other side
        self.loss = loss # chance (0 to 1) that a message is lost
        self.rng = rng # my random number maker (made from a seed)

    def send(self, dest, msg_type, msg_id, payload):
        # pretend the link takes a little time
        time.sleep(DELAY)
        # lose the message at random, otherwise hand it to the other side
        if self.rng.random() < self.loss:
            return
        self.outbox.put(Packet(self.name, msg_type, msg_id, payload))

    def recv(self, timeout):
        # wait up to timeout seconds for a message, None if nothing came
        try:
            return self.inbox.get(timeout=timeout)
        except queue.Empty:
            return None


def run_once(mode, loss, seed):
    # runs ONE transfer and gives back its numbers
    a_to_b = queue.Queue() # messages going from sender to receiver
    b_to_a = queue.Queue() # messages going from receiver to sender
    # each end gets its own random maker, both made from the seed
    sender_net = LossyNet("A", b_to_a, a_to_b, loss, random.Random(seed))
    receiver_net = LossyNet("B", a_to_b, b_to_a, loss, random.Random(seed + 1000))

    if mode == "best effort":
        sender = BestEffortSender(sender_net, min_gap=MIN_GAP)
        receiver = BestEffortReceiver(receiver_net, observe_time=OBSERVE_TIME)
    else:
        sender = ReliableSender(sender_net, timeout=ACK_TIMEOUT, max_retries=5, min_gap=MIN_GAP)
        receiver = ReliableReceiver(receiver_net, linger=0.3, idle_timeout=2.0)

    # the receiver listens in the background while the sender sends
    thread = threading.Thread(target=receiver.run)
    thread.start()
    result = sender.send_all("B", 1, MESSAGES)
    thread.join()

    got = len(receiver.delivered)
    return {
        "delivered": got / len(MESSAGES), # fraction of messages that arrived
        "complete": got == len(MESSAGES), # did the whole sequence arrive?
        "retx": result.retransmissions, # how many resends
        "elapsed": result.elapsed, # seconds the sender spent
    }


def main():
    print(f"{'mode':<14}{'loss':<6}{'seed':<6}{'delivered':<11}{'complete':<10}{'retx':<6}{'elapsed (s)'}")
    for loss in LOSS_LEVELS:
        for mode in ("best effort", "stop and wait"):
            rows = []
            for seed in range(1, RUNS + 1):
                row = run_once(mode, loss, seed)
                rows.append(row)
                print(f"{mode:<14}{loss:<6.0%}{seed:<6}{row['delivered']:<11.2f}"
                      f"{str(row['complete']):<10}{row['retx']:<6}{row['elapsed']:.2f}")
            # one summary line for these 3 runs: averages, plus the range of the times
            times = [r["elapsed"] for r in rows]
            print(f"  average: delivered={statistics.mean(r['delivered'] for r in rows):.2f} "
                  f"retx={statistics.mean(r['retx'] for r in rows):.1f} "
                  f"elapsed={statistics.mean(times):.2f}s (range {min(times):.2f} to {max(times):.2f}s)")


if __name__ == "__main__":
    main()