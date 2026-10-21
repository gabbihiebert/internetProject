# Computer Networks Mini Internet Project

## Overview

This project is a Python-based mini-internet built using UDP sockets.

The project will include:

* 2 end hosts
* 4 routers
* Virtual addresses
* Packet forwarding
* Static forwarding tables
* Packet loss and delay
* Logging and testing

Our team is using **Track B: Reliable Transfer**.

## Team

* Isabelle Cox: reliable transfer (`reliable.py`)
* Gabbi Hiebert: packet format and forwarding (`packet.py`, `forwarding.py`)
* Ali Kaveer: network setup (`config.py`, `netnode.py`, `host.py`, `router.py`)

## Project Structure

* `config.py`, `netnode.py`, `topology.json`: config loading and validation, UDP sockets, loss/delay
* `host.py`, `router.py`: host (echo, probe, reliable, reliable-recv) and router processes
* `packet.py`: defines the packet format
* `forwarding.py`: manages forwarding logic and definitions
* `reliable.py`: Track B stop-and-wait sender and receiver
* `topology_loop.json`: forwarding loop (hop-limit test)
* `topology_lower.json`: lower path via C
* `test_reliable.py`: tests for the reliable transfer code
* `test_packet.py`: tests for the packet format code
* `test_forwarding.py`: tests for the forwarding code

More files will be added as development continues.

## Requirements

* Python 3
* Git
* Wireshark

## Status

Core forwarding, probe/echo, and reliable transfer run on the network. Baseline loss/delay measurements and the Wireshark capture are in progress.

## Running the Project

Each part of the network runs in its own terminal window. Open a new terminal for each command below and run it from the project folder.

**Step 1: Start the 4 routers** (one terminal each)

    python router.py --config topology.json --name A
    python router.py --config topology.json --name B
    python router.py --config topology.json --name C
    python router.py --config topology.json --name D

**Step 2: Start host H2** (it answers any message it receives)

    python host.py --config topology.json --name H2 --mode echo

**Step 3: Send 20 test messages from host H1**

    python host.py --config topology.json --name H1 --mode probe --dst 10.0.0.2 --count 20

When it finishes, the last log line should look like this: `SUMMARY sent=20 received=20 lost=0 success_rate=1.000`

### Reliable transfer (Track B)

Stop H2 with Ctrl+C. Keep the routers running. Start the receiver first, then the sender:

    python host.py --config topology.json --name H2 --mode reliable-recv
    python host.py --config topology.json --name H1 --mode reliable --dst 10.0.0.2 --count 10

When it finishes, the sender's last log line should say `success=True acked=10/10 retx=0`.

### Other demos

Stop all the routers (Ctrl+C in each), then restart all four with a different config file. For example, `python router.py --config topology_lower.json --name A`.

* `topology_lower.json`: messages take the lower path through Router C
* `topology_loop.json`: messages loop between Routers A and B until the hop limit runs out, so the host times out and the router logs say "Hop limit exceeded"

## Tests
    python test_packet.py
    python test_forwarding.py
    python test_reliable.py

## Known Issues
* host.py probe loop can mark a probe as timed out if an older echo arrives late
* delayed packets can be late by up to the receive timeout (0.1s in routers)
* These are issues that were discovered during code reviews and will be adressed after midterms!