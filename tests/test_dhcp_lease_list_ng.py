import importlib.machinery
import json
import os
import subprocess
import sys
import types
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, 'dhcp-lease-list-ng')
SAMPLE = os.path.join(ROOT, 'tests', 'sample.leases')

loader = importlib.machinery.SourceFileLoader('dhcp_lease_list_ng', SCRIPT)
dll = types.ModuleType(loader.name)
loader.exec_module(dll)

NOW = 1798000000  # 2026-12-23 07:46:40 UTC, between the past and the future leases of the sample


def run(*args, **env):
    process = subprocess.Popen([sys.executable, SCRIPT, '-f', SAMPLE] + list(args), env=dict(os.environ, **env),
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    stdout, stderr = process.communicate()
    return process.returncode, stdout, stderr


def sample_leases():
    with open(SAMPLE) as f:
        return dll.parse_dhcp_leases(f.read())


class StripStatementTest(unittest.TestCase):
    def test_comment_after_semicolon(self):
        self.assertEqual(dll.strip_statement('  starts epoch 1; # Thu Jan 01'), 'starts epoch 1')

    def test_semicolon_inside_quotes(self):
        self.assertEqual(dll.strip_statement('client-hostname "a;b";'), 'client-hostname "a;b"')

    def test_escaped_quote(self):
        self.assertEqual(dll.strip_statement(r'uid "\";x";'), r'uid "\";x"')

    def test_no_semicolon(self):
        self.assertEqual(dll.strip_statement('lease 10.0.0.1 {'), 'lease 10.0.0.1 {')


class ParseTimeTest(unittest.TestCase):
    def test_date(self):
        self.assertEqual(dll.parse_time('4 2026/10/29 00:00:00'), 1793232000)

    def test_epoch(self):
        self.assertEqual(dll.parse_time('epoch 1793232000'), 1793232000)

    def test_never(self):
        self.assertIsNone(dll.parse_time('never'))


class ParseLeasesTest(unittest.TestCase):
    def setUp(self):
        self.leases = sample_leases()

    def test_only_lease_blocks(self):
        self.assertEqual([lease['ip_address'] for lease in self.leases],
                         ['10.0.0.20', '10.0.0.20', '10.0.0.5', '10.0.0.7', '10.0.0.30', '10.0.0.9'])

    def test_fields(self):
        lease = self.leases[1]
        self.assertEqual(lease['hardware'], 'aa:bb:cc:00:00:01')
        self.assertEqual(lease['binding-state'], 'active')
        self.assertEqual(lease['next-binding-state'], 'free')
        self.assertEqual(lease['rewind-binding-state'], 'free')
        self.assertEqual(lease['vendor-class-identifier'], 'android-dhcp-14')
        self.assertEqual(lease['client-hostname'], 'pixel')
        self.assertNotIn('next', lease)

    def test_never_and_epoch(self):
        self.assertIsNone(self.leases[2]['ends'])
        self.assertEqual(self.leases[3]['ends'], 4102444800)

    def test_nested_block_ignored(self):
        self.assertNotIn('ClientIP', self.leases[3])
        self.assertEqual(self.leases[3]['client-hostname'], 'semi;colon')

    def test_mac_lowercased(self):
        self.assertEqual(self.leases[3]['hardware'], 'aa:bb:cc:00:00:07')

    def test_flag(self):
        self.assertIs(self.leases[5]['abandoned'], True)


class SelectLeasesTest(unittest.TestCase):
    def setUp(self):
        self.leases = sample_leases()

    def ips(self, keep):
        return [lease['ip_address'] for lease in dll.select_leases(self.leases, keep, NOW)]

    def test_active(self):
        self.assertEqual(self.ips('active'), ['10.0.0.5', '10.0.0.7', '10.0.0.20'])

    def test_last(self):
        self.assertEqual(self.ips('last'), ['10.0.0.5', '10.0.0.7', '10.0.0.9', '10.0.0.20', '10.0.0.30'])

    def test_all(self):
        self.assertEqual(self.ips('all'), ['10.0.0.5', '10.0.0.7', '10.0.0.9', '10.0.0.20', '10.0.0.20', '10.0.0.30'])

    def test_all_keeps_file_order_per_ip(self):
        states = [lease['binding-state'] for lease in dll.select_leases(self.leases, 'all', NOW)
                  if lease['ip_address'] == '10.0.0.20']
        self.assertEqual(states, ['free', 'active'])


class FormatTest(unittest.TestCase):
    def test_expires(self):
        self.assertEqual(dll.format_expires(None, NOW), 'never')
        self.assertEqual(dll.format_expires(NOW - 1, NOW), 'expired')
        self.assertEqual(dll.format_expires(NOW + 3661, NOW), '1:01:01')
        self.assertEqual(dll.format_expires(NOW + 86400 + 59, NOW), '1 day, 0:00:59')
        self.assertEqual(dll.format_expires(NOW + 2 * 86400, NOW), '2 days, 0:00:00')

    def test_time_utc(self):
        self.assertEqual(dll.format_time(1793232000, True), '2026-10-29 00:00:00')
        self.assertEqual(dll.format_time(None, True), 'never')


class CliTest(unittest.TestCase):
    def test_table(self):
        code, out, _ = run()
        self.assertEqual(code, 0)
        self.assertIn('Total Leases: 3', out)
        lines = [line for line in out.splitlines() if line.startswith(('+', '|'))]
        self.assertEqual(len(set(len(line) for line in lines)), 1, 'table rows differ in width')

    def test_json_local_time(self):
        code, out, _ = run('-j', TZ='TST-03')
        self.assertEqual(code, 0)
        lease = [lease for lease in json.loads(out) if lease['ip_address'] == '10.0.0.7'][0]
        self.assertEqual(lease['ends'], '2100-01-01 03:00:00')

    def test_json_utc(self):
        _, out, _ = run('-j', '-u', TZ='TST-03')
        lease = [lease for lease in json.loads(out) if lease['ip_address'] == '10.0.0.7'][0]
        self.assertEqual(lease['ends'], '2100-01-01 00:00:00')

    def test_parsable(self):
        code, out, _ = run('--parsable', TZ='TST-03')
        self.assertEqual(code, 0)
        self.assertIn('MAC aa:bb:cc:00:00:07 IP 10.0.0.7 HOSTNAME semi;colon BEGIN 2026-10-29 00:00:00 '
                      'END 2100-01-01 00:00:00 MANUFACTURER -NA-', out.splitlines())

    def test_conflicting_options(self):
        code, _, err = run('-a', '--last')
        self.assertEqual(code, 2)
        self.assertIn('not allowed', err)

    def test_missing_file(self):
        code, _, err = run('-f', '/nonexistent/dhcpd.leases')
        self.assertEqual(code, 1)
        self.assertIn('No such file', err)


if __name__ == '__main__':
    unittest.main()
