# dhcp-lease-list-ng

## What

List the leases of an ISC DHCP server (`dhcpd`) as a readable table, JSON or one line per lease.

A drop-in replacement for `dhcp-lease-list`, the Perl script that Debian and Ubuntu install with the
`isc-dhcp-server` package. One file, Python standard library only, runs on any Python 3.4 or newer, so it works out
of the box on every Debian and Ubuntu release that still ships ISC DHCP.

```
$ sudo dhcp-lease-list-ng
+--------------+-------------------+----------+-----------------+-----------------+-------------------------+---------------+
|                                                    DHCPD LEASES STATUS                                                    |
+--------------+-------------------+----------+-----------------+-----------------+-------------------------+---------------+
|  IP Address  |    MAC Address    | Expires  | Client Hostname |    DDNS-Name    | Vendor Class Identifier | Binding State |
+--------------+-------------------+----------+-----------------+-----------------+-------------------------+---------------+
| 192.168.1.10 | 3c:22:fb:12:34:56 | 10:59:58 | macbook-air     |                 |                         | active        |
| 192.168.1.23 | d8:3a:dd:ab:cd:ef |  0:34:59 | raspberrypi     | raspberrypi.lan |                         | active        |
| 192.168.1.41 | a4:cf:12:9e:00:11 | 11:49:59 | pixel-8         |                 | android-dhcp-14         | active        |
| 192.168.1.57 | b8:27:eb:01:02:03 |    never | printer         |                 |                         | active        |
+--------------+-------------------+----------+-----------------+-----------------+-------------------------+---------------+
Total Leases: 4
Report generated: 2026-10-28 18:44:38
```

## Why

Although **ISC DHCP (`dhcpd`) officially reached End of Life in 2022**, with its last maintenance release on
October 5, 2022 (see the [announcement by the Internet Systems Consortium of October 4, 2022](https://www.isc.org/blogs/isc-dhcp-eol/)),
it remains widely deployed.

ISC discontinued maintenance of the legacy DHCP server and recommends migrating to its modern replacement,
[Kea DHCP](https://www.isc.org/dhcp_migration/).

The scale of its continued usage is illustrated by Debian's Popularity Contest statistics: as of mid-2025,
approximately **8,000 participating Debian systems still had `isc-dhcp-server` installed**, compared to only around
**180 installations of Kea**, according to a [discussion among Debian developers](https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=1106121).

These numbers represent only a voluntary sample of Debian installations, not worldwide deployment figures. The actual
global installed base remains unknown, but the data demonstrates that ISC DHCP continued to have a substantial
presence years after its official EOL. Debian 13 (trixie) still ships it, but the package was removed from Debian
testing in February 2026, so it is not expected in Debian 14.

So many admins still read `dhcpd.leases` every day, and the script for it deserves a better version. The original
`dhcp-lease-list` works, but:

- it shows only MAC, IP, hostname, end date and manufacturer, and cuts hostnames at 14 characters;
- it prints dates in UTC, so on a server in any other time zone you have to convert them in your head;
- it has no JSON output;
- its manufacturer lookup reads `/usr/share/misc/oui.txt`, but the Debian/Ubuntu `ieee-data` package installs the
  file as `/usr/share/ieee-data/oui.txt`, so on those systems the lookup never works;
- it silently skips leases without an end date, such as infinite (`ends never;`) leases.

`dhcp-lease-list-ng` also shows the DDNS name, the vendor class identifier and the binding state, shows the time
left until each lease expires, sizes the table columns to fit the data, and prints times in local time.

## Install

```sh
sudo curl -fsSL -o /usr/local/sbin/dhcp-lease-list-ng \
    https://raw.githubusercontent.com/adel-s/dhcp-lease-list-ng/master/dhcp-lease-list-ng
sudo chmod 755 /usr/local/sbin/dhcp-lease-list-ng
```

Requirements: Python 3.4+. The table and `--parsable` output also work with only `python3-minimal` installed;
`--json` needs the full `python3` package on Ubuntu, whose minimal package has no `json` module.

The leases file is usually readable by root only, so run the script with `sudo`.

## Usage

```
dhcp-lease-list-ng [-h] [-a | -l] [-j | -p] [-f FILE] [-u] [-V]
```

| Option                    | Meaning                                                                   |
|---------------------------|---------------------------------------------------------------------------|
| *(none)*                  | the current active lease of every IP address                              |
| `-a`, `--all`             | every record from the leases file, including expired and superseded ones  |
| `-l`, `--last`            | the last record of every MAC address, even if it has expired              |
| `-j`, `--json`            | JSON output with all fields of each lease                                 |
| `-p`, `--parsable`        | one line per lease in the format of the Perl `dhcp-lease-list --parsable` |
| `-f`, `--file`, `--lease` | leases file to read                                                       |
| `-u`, `--utc`             | show times in UTC instead of local time                                   |
| `-V`, `--version`         | show the version                                                          |
| `-h`, `--help`            | show the help                                                             |

Without `--file` the script reads the first file it finds of `/var/db/dhcpd.leases`, `/var/lib/dhcp/dhcpd.leases`,
`/var/lib/dhcp3/dhcpd.leases` and `/var/lib/dhcpd/dhcpd.leases`.

### JSON

```
$ sudo dhcp-lease-list-ng -j
[
    {
        "ip_address": "192.168.1.10",
        "starts": "2026-10-28 17:44:38",
        "ends": "2026-10-29 05:44:37",
        "binding-state": "active",
        "hardware": "3c:22:fb:12:34:56",
        "client-hostname": "macbook-air",
        "expires": "10:59:58"
    },
    ...
]
```

Every statement of a lease block becomes a key: `set` variables (`ddns-fwd-name`, `vendor-class-identifier`, ...)
under their own names, `binding state`, `next binding state` and `rewind binding state` as `binding-state`,
`next-binding-state` and `rewind-binding-state`, flags such as `abandoned` as `true`. Times are
`YYYY-MM-DD HH:MM:SS` in local time (UTC with `--utc`) or `never`; `expires` is the time left, `expired` or `never`.
If an `oui.txt` file is found (see below), a `manufacturer` key is added.

### Parsable output

```
$ sudo dhcp-lease-list-ng --parsable
MAC 3c:22:fb:12:34:56 IP 192.168.1.10 HOSTNAME macbook-air BEGIN 2026-10-28 21:44:38 END 2026-10-29 09:44:37 MANUFACTURER -NA-
```

The same line format as the Perl script, so existing scripts that parse it keep working. As in the original, the
dates in this format are always in UTC.

### Manufacturer names

`--json` and `--parsable` add the manufacturer of each MAC address if an IEEE `oui.txt` file is found at
`/usr/share/ieee-data/oui.txt` (the `ieee-data` package), `/usr/share/misc/oui.txt` or `/usr/local/etc/oui.txt`.

## Drop-in replacement for the original

The options of the Perl script work the same way:

| Perl `dhcp-lease-list` | `dhcp-lease-list-ng`  | Note                                               |
|------------------------|-----------------------|----------------------------------------------------|
| *(none)*               | *(none)*              | the table has more columns, times in local time    |
| `--all`                | `--all`               |                                                    |
| `--last`               | `--last`              |                                                    |
| `--parsable`           | `--parsable`          | same line format                                   |
| `--lease FILE`         | `--lease FILE`        |                                                    |
| `--help`               | `--help`              |                                                    |

To make `dhcp-lease-list` itself run the new script, divert the packaged one so that package upgrades do not
overwrite the link:

```sh
sudo dpkg-divert --local --rename --add /usr/sbin/dhcp-lease-list
sudo ln -s /usr/local/sbin/dhcp-lease-list-ng /usr/sbin/dhcp-lease-list
```

## Notes

- IPv4 leases only (`dhcpd.leases`); DHCPv6 leases (`dhcpd6.leases`) are not supported yet.

## Development

I don't accept pull requests, sorry: my code, my rules. But if something doesn't work or you need a new feature,
feel free to open an issue and I'll fix it ASAP.

## License

MIT, see [LICENSE](LICENSE).
