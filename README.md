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

* Isabelle Cox
* Gabbi Hiebert
* Ali Kaveer

## Project Structure

* `reliable.py`: Track B stop-and-wait sender and receiver
* `test_reliable.py`: tests for the reliable transfer code
* 'packet.py': defines the packet format
* 'test_packet.py': tests for the packet format code
* forwarding.py': manages forwarding logic and definitions
* test_forwarding.py': tests for the forwarding code

More files will be added as development continues.

## Requirements

* Python 3
* Git
* Wireshark

## Status

Currently beginning implementation for reliable transfer and packet format.

### Initial Responsibilities

* **Network setup:** UDP sockets, configuration, virtual addresses, and host/router processes
* **Packets and forwarding:** Packet format, parsing, forwarding tables, hop limits, return paths, and error handling
* **Reliable transfer:** ACKs, sequence numbers, timeouts, retransmissions, duplicate detection, and ordered delivery

All team members will participate in testing, integration, experiments, and code review.

## Running the Project

Full run instructions will be added as the project is developed.

To run the packet tests: 
    python test_packet.py

To run the forwarding tests: 
    python test_forwarding.py

To run the reliable transfer tests:

    python test_reliable.py
