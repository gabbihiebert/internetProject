# config.py - load and validate the topology configuration file.

import json


class ConfigError(Exception):
    # Raised on any invalid configuration; message names the bad device/field.
    pass


class Config:
    # Holds devices, links, and forwarding tables parsed from topology JSON.

    def __init__(self, raw: dict):
        # Parse and validate raw config dict; raise ConfigError on any problem.
        self._devices = {}
        self._neighbors = {}
        self._links = {}
        self._tables = {}

        self._load(raw)

    # ---------------- accessors ----------------
    def device(self, name: str) -> dict:
        # Return the device record (name, type, virtual_addr, udp_port, udp_host).
        return self._devices[name]

    def neighbors(self, name: str) -> list:
        # Return the list of configured neighbor device names for a device.
        return list(self._neighbors.get(name, []))

    def endpoint(self, name: str) -> tuple:
        # Return the (host, port) UDP endpoint that implements this device.
        d = self._devices[name]

        return (d["udp_host"], d["udp_port"])

    def forwarding_table(self, name: str) -> dict:
        # Return a copy of the static forwarding table {dst_vaddr: neighbor_name}.
        return dict(self._tables.get(name, {}))

    def link_condition(self, a: str, b: str) -> dict:
        # Return {'delay_ms': float, 'loss': float} for the directed link a->b.
        return dict(self._links.get((a, b), {"delay_ms": 0.0, "loss": 0.0}))

    def name_for_port(self, port: int):
        # Return the device name whose UDP port matches, or None.
        for d in self._devices.values():
            if d["udp_port"] == port:
                return d["name"]

        return None

    def name_for_vaddr(self, vaddr: str):
        # Return the device name whose virtual address matches, or None.
        for d in self._devices.values():
            if d["virtual_addr"] == vaddr:
                return d["name"]

        return None

    # ---------------- loader ----------------
    def _load(self, raw: dict):
        # Validate devices, links, and forwarding tables; populate internal dicts.
        if "devices" not in raw:
            raise ConfigError("config missing 'devices'")

        seen_vaddr, seen_port = {}, {}

        for d in raw["devices"]:
            for k in ("name", "type", "virtual_addr", "udp_port"):
                if k not in d:
                    raise ConfigError(f"device {d.get('name', '?')} missing '{k}'")

            if d["type"] not in ("host", "router"):
                raise ConfigError(f"device {d['name']}: type must be host or router")

            if d["virtual_addr"] in seen_vaddr:
                raise ConfigError(
                    f"duplicate virtual_addr {d['virtual_addr']} "
                    f"({seen_vaddr[d['virtual_addr']]} and {d['name']})")

            if d["udp_port"] in seen_port:
                raise ConfigError(
                    f"duplicate udp_port {d['udp_port']} "
                    f"({seen_port[d['udp_port']]} and {d['name']})")

            if not (1024 <= d["udp_port"] <= 65535):
                raise ConfigError(f"device {d['name']}: udp_port out of range")

            seen_vaddr[d["virtual_addr"]] = d["name"]
            seen_port[d["udp_port"]] = d["name"]
            d.setdefault("udp_host", "127.0.0.1")

            self._devices[d["name"]] = d
            self._neighbors[d["name"]] = []

        for link in raw.get("links", []):
            a, b = link.get("a"), link.get("b")

            if a not in self._devices:
                raise ConfigError(f"link references unknown device '{a}'")

            if b not in self._devices:
                raise ConfigError(f"link references unknown device '{b}'")

            if a == b:
                raise ConfigError(f"link {a}-{b} is a self-loop")

            cond = {
                "delay_ms": float(link.get("delay_ms", 0)),
                "loss": float(link.get("loss", 0.0)),
            }

            if cond["delay_ms"] < 0:
                raise ConfigError(f"link {a}-{b}: delay_ms must be >= 0")

            if not (0.0 <= cond["loss"] <= 1.0):
                raise ConfigError(f"link {a}-{b}: loss must be in [0,1]")

            self._links[(a, b)] = cond
            self._links[(b, a)] = dict(cond)

            if b not in self._neighbors[a]:
                self._neighbors[a].append(b)

            if a not in self._neighbors[b]:
                self._neighbors[b].append(a)

        for dev, table in raw.get("forwarding_tables", {}).items():
            if dev not in self._devices:
                raise ConfigError(f"forwarding table for unknown device '{dev}'")

            for dest, nh in table.items():
                if nh not in self._neighbors.get(dev, []):
                    raise ConfigError(
                        f"forwarding table {dev}: next hop '{nh}' for {dest} "
                        f"is not a configured neighbor")

            self._tables[dev] = dict(table)


def load(path: str) -> Config:
    # Open and parse topology JSON, raising ConfigError on file or syntax problems.
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)

    except FileNotFoundError:
        raise ConfigError(f"config file not found: {path}")

    except json.JSONDecodeError as e:
        raise ConfigError(f"config file {path} is not valid JSON: {e}")

    return Config(raw)