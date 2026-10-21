"""
Track B: stop and wait reliable transfer over the mini internet.

My job: make sure every message arrives, in order, with no repeats,
even if the network loses some of them.

This file does NOT touch sockets. It talks to the network through a
"transport" object that my teammates' host code will provide:

network.send(dest, msg_type, msg_id, payload) # payload is bytes
network.recv(timeout) -> Packet or None # None means timed out

Packet needs .src, .msg_type, .msg_id, .payload.

I send numbered messages one at a time. After each one I wait
for a "got it" message (an ACK). If no ACK comes back in time, I send
the same message again.

"""

# useful modules for manipulating bytes/timing and for logging events
import logging
import struct
import time
from collections import namedtuple

log = logging.getLogger("reliable")

# my message types are text, because packet.py turns every type into text when it sends
MSG_RDATA = "RDATA"
MSG_RACK = "RACK"

# reliable transfer information inside each message
# run_id (4 bytes), seq (4 bytes), flags (1 byte) -> 9 bytes, big endian
HDR = struct.Struct("!IIB")
FLAG_LAST = 0x01
MAX_DATA = 1000  # under the 1,200 byte limit

# holds sender, type, id, and contents
Packet = namedtuple("Packet", "src msg_type msg_id payload")
# returns results, timing, successes, failures, resends, etc
SendResult = namedtuple("SendResult", "success delivered_acked total_msgs data_sent retransmissions elapsed reason")


def encode(run_id, seq, flags, data=b""):
    # pack the header numbers + the actual message into bytes to send
    # refuse messages that are too big for one packet
    if len(data) > MAX_DATA:
        raise ValueError(f"message too large ({len(data)} > {MAX_DATA})")
    return HDR.pack(run_id, seq, flags) + data


def decode(payload):
    # open received bytes. return (run_id, seq, flags, data) or None if malformed.
    # too short to even hold a header = broken message, ignore it
    if len(payload) < HDR.size:
        return None
    run_id, seq, flags = HDR.unpack_from(payload)
    return run_id, seq, flags, payload[HDR.size:]


class ReliableSender:
    """
    Stop and wait sender: at most ONE unconfirmed message at a time!!

    States: SENDING (data out, waiting for ACK) -> next message -> ... -> DONE
    or FAILED once we run out of resends.

    """

    def __init__(self, network, timeout=0.5, max_retries=5, min_gap=0.0):
        self.network = network # how we send/receive (teammates' code)
        self.timeout = timeout  # seconds to wait for an ACK before resending
        self.max_retries = max_retries # most resends per message before giving up
        self.min_gap = min_gap # smallest pause between sends (speed limit)
        self._last_send_time = float("-inf") # when we last sent (never, at first)

    def _send(self, dest, run_id, seq, flags, data, try_number):
        # send one data message (this is the helper that actually sends)
        # speed limit: if we sent too recently, pause until enough time passed
        pause = self._last_send_time + self.min_gap - time.monotonic()
        if pause > 0:
            time.sleep(pause)
        # remember when we sent, then hand the message to the network
        self._last_send_time = time.monotonic()
        self.network.send(dest, MSG_RDATA, seq, encode(run_id, seq, flags, data))
        log.info("event=send run=%s type=DATA seq=%d attempt=%d", run_id, seq, try_number)

    def send_all(self, dest, run_id, messages):
        # send every message in the list, one at a time, reliably
        start = time.monotonic()
        total = len(messages)
        # counters: all sends, resends only, and messages confirmed by an ACK
        data_sent = resends = confirmed = 0

        # go through the messages in order, seq is the message number
        for seq, data in enumerate(messages):
            # mark the final message so the receiver knows it's the end
            flags = FLAG_LAST if seq == total - 1 else 0
            try_number = 0

            # keep trying this ONE message until it is confirmed (or we give up)
            while True:
                # too many tries -> give up (so we never wait forever)
                if try_number > self.max_retries:
                    log.error("event=fail run=%s seq=%d reason=retry_limit", run_id, seq)
                    return SendResult(False, confirmed, total, data_sent, resends,
                    time.monotonic() - start, f"retry limit at seq {seq}")
                try_number += 1
                data_sent += 1
                # anything after the first try is a resend
                if try_number > 1:
                    resends += 1
                self._send(dest, run_id, seq, flags, data, try_number)

                # got the ACK? then count it and move on to the next message
                if self._wait_for_ack(dest, run_id, seq):
                    confirmed += 1
                    break
                # no ACK in time: note it, and the loop sends the message again
                log.warning("event=timeout run=%s seq=%d attempt=%d", run_id, seq, try_number)

        # every message was confirmed
        return SendResult(True, confirmed, total, data_sent, resends, time.monotonic() - start, "ok")

    def _wait_for_ack(self, dest, run_id, seq):
        # wait for the ACK of this one message. True = got it, False = timed out
        # the latest time we're willing to keep waiting
        deadline = time.monotonic() + self.timeout
        while True:
            time_left = deadline - time.monotonic()
            # out of time -> no ACK
            if time_left <= 0:
                return False
            # check for incoming messages, waiting at most time_left seconds
            packet = self.network.recv(time_left)
            if packet is None:
                return False
            # only look inside it if it is an ACK-type message
            info = decode(packet.payload) if packet.msg_type == MSG_RACK else None
            # is it the right ACK? same batch, same message number, from the right place
            if info and info[0] == run_id and info[1] == seq and packet.src == dest:
                log.info("event=ack run=%s seq=%d", run_id, seq)
                return True
            # anything else (a late ACK for an older message, wrong batch, junk): ignore it
            log.info("event=ignore_ack run=%s got=%r", run_id, info and info[:2])


class ReliableReceiver:
    """
    Keeps each message once, in order, and sends an ACK for every data
    message it sees (even repeats, so a lost ACK can't get the sender stuck).

    After the final message it stays listening for "linger" seconds, in case
    the last ACK got lost and the sender sends the last message again.
    "idle_timeout" stops us from waiting forever if nothing ever arrives.

    """

    def __init__(self, network, linger=2.0, idle_timeout=30.0, on_deliver=None):
        self.network = network
        self.linger = linger # seconds to keep listening after the last message
        self.idle_timeout = idle_timeout # seconds to wait with no new message before giving up
        self.on_deliver = on_deliver # function to call for each kept message
        self.delivered = [] # the kept messages, as (seq, data), in order
        self.duplicates = 0 # how many repeats we saw
        self.complete = False # True once the last message is kept

    def run(self):
        # listen for messages until the transfer is finished
        my_run_id = None # the batch we're accepting (set by the first message)
        expected_seq = 0 # the message number we want next
        last_arrival = time.monotonic() # when the last message of my batch arrived

        while True:
            now = time.monotonic()
            # all done and we've listened long enough afterwards: stop
            if self.complete and now - last_arrival >= self.linger:
                return
            # nothing has ever arrived and we've waited too long: stop
            if not self.complete and now - last_arrival > self.idle_timeout:
                log.error("event=receiver_idle_timeout")
                return

            # peek at the mailbox for a moment, skip if empty or not a data message
            packet = self.network.recv(0.05)
            if packet is None or packet.msg_type != MSG_RDATA:
                continue

            # open it, if it's garbage, note it and ignore it
            info = decode(packet.payload)
            if info is None:
                log.warning("event=drop reason=malformed_reliable_payload")
                continue
            run_id, seq, flags, data = info

            # the first batch we see becomes "our" batch, ignore other batches
            if my_run_id is None:
                my_run_id = run_id
            if run_id != my_run_id:
                log.warning("event=ignore run=%s reason=other_run", run_id)
                continue
            last_arrival = time.monotonic()

            if seq == expected_seq:
                # the message we wanted: keep it, and look for the next number
                self.delivered.append((seq, data))
                if self.on_deliver:
                    self.on_deliver(seq, data)
                expected_seq += 1
                # if it was the last one, we are complete
                if flags & FLAG_LAST:
                    self.complete = True
                log.info("event=deliver run=%s seq=%d", run_id, seq)
                self._ack(packet.src, run_id, seq)
            elif seq < expected_seq:
                # a repeat of something we already kept: don't keep it again,
                # but DO send the ACK again (our first ACK was probably lost)
                self.duplicates += 1
                log.info("event=duplicate run=%s seq=%d", run_id, seq)
                self._ack(packet.src, run_id, seq)
            else:
                # a number from the future: shouldn't happen with stop-and-wait,
                # so note it and don't ACK
                log.warning("event=out_of_order run=%s seq=%d expected=%d", run_id, seq, expected_seq)

    def _ack(self, dest, run_id, seq):
        # send a 'got it' message for message number seq
        self.network.send(dest, MSG_RACK, seq, encode(run_id, seq, 0))
        log.info("event=send run=%s type=ACK seq=%d", run_id, seq)