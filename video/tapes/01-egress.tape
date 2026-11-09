# Shot 1 (hook): the agent's shell tries the internet. example.com is denied, PyPI is allowed.
Output video/out/01-egress.mp4
Source video/tapes/_setup.tape
Type "python chat.py sample-data/cost-export-2026-11-01.csv --output-dir outputs/egress \"
Enter
Type `  --prompt 'Network test only. Use shell to run: curl -sS -m 15 -o /dev/null -w "%{http_code}\n" https://example.com ; curl -sS -m 15 -o /dev/null -w "%{http_code}\n" https://pypi.org/simple/ and reply with the raw output.'`
Enter
Wait+Screen@240s /Agent:/
Sleep 6s
