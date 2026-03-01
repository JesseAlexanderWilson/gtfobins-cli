# gtfobins-cli

A CLI tool for checking SUID binaries against the [GTFOBins](https://gtfobins.github.io/) database. Useful during privilege escalation enumeration on Linux systems.

## Features

- Automatically finds SUID binaries on the current system
- Checks them against the GTFOBins database
- Categorises results into three tiers: exploitable, expected defaults, and unknown
- Supports reading from a file or stdin
- Built-in database update via the GTFOBins API

## Installation

```bash
git clone https://github.com/jessewilson/gtfobins-cli /opt/gtfobins-cli
cd /opt/gtfobins-cli
sudo bash install.sh
```

Or as a one-liner:

```bash
curl -s https://raw.githubusercontent.com/jessewilson/gtfobins-cli/main/install.sh | sudo bash
```

## Usage

**Scan the current system for SUID binaries:**
```bash
gtfobins
```

**Check a file containing a list of binaries:**
```bash
gtfobins --file results.txt
```

**Pipe output from find directly:**
```bash
find / -type f -perm -04000 -ls 2>/dev/null | gtfobins
```

**Update the GTFOBins database:**
```bash
gtfobins --update
```

**Show version info:**
```bash
gtfobins --version
```

**Save results to a file:**
```bash
gtfobins --file results.txt > output.txt
```

## Output

Results are split into three categories:

- **FOUND IN GTFOBINS** — binaries with known exploitation techniques
- **DEFAULT SUID** — expected system binaries, not interesting
- **UNKNOWN SUID** — not in GTFOBins and not a known default — worth investigating

## Requirements

- Python 3.10+
- Linux
- Internet access for `--update`

## License

MIT License — Copyright (c) 2026 Jesse Wilson

See [LICENSE](LICENSE) for full text.

## Acknowledgements

This tool uses data from [GTFOBins](https://gtfobins.github.io/) by [@norbemi](https://twitter.com/norbemi) and [@cyrus_and](https://twitter.com/cyrus_and).
