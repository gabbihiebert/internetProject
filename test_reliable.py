"""
Tests for my stop and wait reliable transfer (reliable.py).

These tests check that my sender and receiver work correctly on their own.
They use a small stand-in network that passes messages back and forth in
memory, so the tests can run at any time, no matter which other parts of
the project are finished yet. When the real network is ready, my code only
needs the same two calls (send and recv), so these tests still describe how
my part should behave.

To run them: python test_reliable.py

"""

# modules for waiting on messages, running two things at once, and testing
import queue
import threading
import unittest

from reliable import (ReliableSender, ReliableReceiver, Packet, encode, decode, MSG_RDATA, MSG_RACK, MAX_DATA)


class FakeNet:
    # one end of my fake network (the sender has one, the receiver has one)
    def __init__(self, name, inbox, outbox, drops, lose_all=False):
        self.name = name # who I am, like "A" or "B"
        self.inbox = inbox # where messages for me wait
        self.outbox = outbox # where I put messages for the other side
        self.drops = drops # (type, seq) pairs to lose, each only once
        self.lose_all = lose_all # True = lose everything I send

    def send(self, dest, msg_type, msg_id, payload):
        # lose everything if this end is "broken"
        if self.lose_all:
            return
        # lose this message ONE time if it is on my drop list
        if (msg_type, msg_id) in self.drops:
            self.drops.remove((msg_type, msg_id))
            return
        # otherwise hand it to the other side
        self.outbox.put(Packet(self.name, msg_type, msg_id, payload))

    def recv(self, timeout):
        # wait up to timeout seconds for a message, None if nothing came
        try:
            return self.inbox.get(timeout=timeout)
        except queue.Empty:
            return None


def run_transfer(messages, drops=None, lose_all=False):
    # runs one whole transfer and gives back (sender result, receiver)
    drops = drops if drops is not None else []
    a_to_b = queue.Queue() # messages going from sender to receiver
    b_to_a = queue.Queue() # messages going from receiver to sender
    sender_net = FakeNet("A", b_to_a, a_to_b, drops, lose_all)
    receiver_net = FakeNet("B", a_to_b, b_to_a, drops)

    # short times so my tests run fast
    receiver = ReliableReceiver(receiver_net, linger=0.3, idle_timeout=0.5)
    sender = ReliableSender(sender_net, timeout=0.05, max_retries=3)

    # the receiver listens in the background while the sender sends
    thread = threading.Thread(target=receiver.run)
    thread.start()
    result = sender.send_all("B", 1, messages)
    thread.join(timeout=5)
    return result, receiver


class TestReliable(unittest.TestCase):
    def setUp(self):
        # my test messages: five small messages
        self.msgs = [b"one", b"two", b"three", b"four", b"five"]

    def test_no_loss(self):
        # nothing lost: everything arrives in order, once, no resends
        result, receiver = run_transfer(self.msgs)
        self.assertTrue(result.success)
        self.assertEqual([d for _, d in receiver.delivered], self.msgs)
        self.assertEqual(receiver.duplicates, 0)
        self.assertEqual(result.retransmissions, 0)

    def test_dropped_data_message(self):
        # I lose data message 2 once: sender should resend it and recover
        result, receiver = run_transfer(self.msgs, drops=[(MSG_RDATA, 2)])
        self.assertTrue(result.success)
        self.assertEqual([d for _, d in receiver.delivered], self.msgs)
        self.assertEqual(result.retransmissions, 1)

    def test_dropped_last_ack(self):
        # I lose the ACK of the LAST message once: the sender resends it,
        # the receiver sees a repeat, keeps it only once, and ACKs again
        last = len(self.msgs) - 1
        result, receiver = run_transfer(self.msgs, drops=[(MSG_RACK, last)])
        self.assertTrue(result.success)
        self.assertEqual([d for _, d in receiver.delivered], self.msgs)
        self.assertEqual(receiver.duplicates, 1)
        self.assertTrue(receiver.complete)

    def test_unreachable_destination(self):
        # nothing gets through: sender must give up, not wait forever
        result, receiver = run_transfer(self.msgs, lose_all=True)
        self.assertFalse(result.success)
        self.assertEqual(result.delivered_acked, 0)

    def test_encode_decode(self):
        # packing then unpacking gives back what I put in
        raw = encode(7, 3, 1, b"hi")
        self.assertEqual(decode(raw), (7, 3, 1, b"hi"))

    def test_malformed_and_too_big(self):
        # junk that is too short is rejected, oversized data raises an error
        self.assertIsNone(decode(b"abc"))
        with self.assertRaises(ValueError):
            encode(1, 0, 0, b"x" * (MAX_DATA + 1))


if __name__ == "__main__":
    unittest.main()