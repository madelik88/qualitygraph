from email import message_from_bytes
from html import unescape
from io import BytesIO
import json
from pathlib import Path
import re
import shutil
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from urllib.parse import urlencode

from qualitygraph import index_snapshot, investigate, load_csv
from qualitygraph_store import save_snapshot
from qualitygraph_web import BrowserHandler


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "synthetic"


class WebTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.database = self.directory / "qualitygraph.db"
        tables, digests = load_csv(EXAMPLE)
        index_snapshot(tables)
        self.snapshot, _ = save_snapshot(self.database, tables, digests)

    def request(self, route, host="127.0.0.1:8765"):
        # Exercise the standard-library HTTP parser without opening a server port.
        incoming = BytesIO(f"GET {route} HTTP/1.1\r\nHost: {host}\r\n\r\n".encode())
        payload = bytearray()
        connection = Mock()
        connection.makefile.return_value = incoming
        connection.sendall.side_effect = payload.extend
        server = SimpleNamespace(
            server_port=8765,
            database=self.database,
            stylesheet=(ROOT / "qualitygraph_web.css").read_text(encoding="utf-8"),
        )
        with patch.object(BrowserHandler, "log_message"):
            BrowserHandler(connection, ("127.0.0.1", 0), server)
        head, body = bytes(payload).split(b"\r\n\r\n", 1)
        status, headers = head.split(b"\r\n", 1)
        return int(status.split()[1]), message_from_bytes(headers), body.decode("utf-8")

    def test_investigation_and_download(self):
        status, _, home = self.request("/")
        self.assertEqual(status, 200)
        self.assertIn('id="snapshot"', home)
        self.assertIn('value="QC-017"', home)
        self.assertNotIn('value="QC-001"', home)

        query = urlencode({"snapshot": self.snapshot, "result": "QC-017"})
        status, _, page = self.request("/?" + query)
        self.assertEqual(status, 200)
        for batch in ("INT-001", "RAW-100", "RAW-200", "FG-010", "FG-011"):
            self.assertIn(batch, page)
        self.assertNotIn("FG-090", page)
        self.assertIn("FG-011</strong> · Lacuna dichiarata", page)
        for record in range(2, 6):
            self.assertIn(f'href="#lineage-{record}"', page)
            self.assertIn(f'id="lineage-{record}"', page)

        link = re.search(r'href="(/report.json\?[^"]+)"', page)
        self.assertIsNotNone(link)
        status, headers, body = self.request(unescape(link.group(1)))
        self.assertEqual(status, 200)
        self.assertEqual(headers.get_content_type(), "application/json")
        self.assertIn("attachment", headers["Content-Disposition"])
        self.assertEqual(json.loads(body), investigate(EXAMPLE, "QC-017"))

    def test_selects_saved_snapshot_and_escapes_source_values(self):
        exports = self.directory / "exports"
        shutil.copytree(EXAMPLE, exports)
        batches = exports / "batches.csv"
        batches.write_text(
            batches.read_text(encoding="utf-8").replace("Resina base", "<b>Resina</b>"),
            encoding="utf-8",
        )
        new_snapshot, _ = save_snapshot(self.database, *load_csv(exports))
        status, _, current = self.request("/?result=QC-017")
        self.assertEqual(status, 200)
        self.assertIn(f'value="{new_snapshot}" selected', current)
        self.assertIn("&lt;b&gt;Resina&lt;/b&gt;", current)
        self.assertNotIn("<b>Resina</b>", current)

        status, _, previous = self.request(f"/?snapshot={self.snapshot}&result=QC-017")
        self.assertEqual(status, 200)
        self.assertIn("Resina base", previous)
        self.assertNotIn("&lt;b&gt;", previous)

    def test_routes_handle_bad_input(self):
        status, headers, _ = self.request("/style.css")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get_content_type(), "text/css")
        self.assertEqual(self.request("/report.json?result=QC-017")[0], 400)
        self.assertEqual(self.request("/?result=QC-001")[0], 400)
        self.assertEqual(self.request("/?snapshot=unknown")[0], 400)
        self.assertEqual(self.request("/missing")[0], 404)
        self.assertEqual(self.request("/", host="example.org")[0], 400)


if __name__ == "__main__":
    unittest.main()
