"""Serve the QualityGraph investigation screen on localhost."""

import argparse
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sqlite3
from urllib.parse import parse_qs, urlencode, urlsplit

from qualitygraph import build_report
from qualitygraph_store import list_snapshots, load_snapshot


def options_html(choices, selected):
    return "".join(
        f'<option value="{escape(value)}"{" selected" if value == selected else ""}>'
        f"{escape(label)}</option>"
        for value, label in choices
    )


PAGE_SIZE = 50


def batch_list(title, items, total):
    cards = []
    for item in items:
        batch = item["batch"]
        steps = []
        for edge in item["path"]:
            record = edge["source"]["record"]
            steps.append(
                f'<li><span>{escape(edge["parent_batch"])} → {escape(edge["child_batch"])}</span>'
                f'<a href="#lineage-{record}">lineage.csv · record {record}</a></li>'
            )
        n_steps = len(steps)
        step_label = "1 passaggio" if n_steps == 1 else f"{n_steps} passaggi"
        cards.append(f"""
            <details class="batch">
              <summary><strong>{escape(batch["batch_id"])}</strong>
                <span>{escape(batch["material"])}</span><small>{step_label}</small></summary>
              <ol class="steps">{"".join(steps)}</ol>
            </details>
        """)
    empty = "Nessun lotto in questa pagina." if total else "Nessun lotto collegato nelle fonti."
    content = "".join(cards) or f'<p class="muted">{empty}</p>'
    return f'<section class="panel"><h3>{title} <span class="count">{total}</span></h3>{content}</section>'


def evidence_rows(items):
    records = {}
    for item in items:
        for edge in item["path"]:
            records[edge["source"]["record"]] = edge

    rows = []
    for record, edge in sorted(records.items()):
        rows.append(f"""
            <tr id="lineage-{record}" tabindex="-1">
              <th scope="row">lineage.csv · record {record}</th>
              <td>{escape(edge["parent_batch"])}</td>
              <td>{escape(edge["child_batch"])}</td>
              <td>{escape(edge["operation_id"])}</td>
            </tr>
        """)
    return "".join(rows)


def pagination_html(query, page, page_count):
    if page_count == 1:
        return ""

    def link(target, label):
        url = escape(f"/?{query}&page={target}") + "#paths"
        return f'<a class="button secondary" href="{url}">{label}</a>'

    previous = link(page - 1, "Precedente") if page > 1 else ""
    following = link(page + 1, "Successiva") if page < page_count else ""
    return (
        '<nav id="paths" class="pagination" aria-label="Pagine dell’indagine">'
        f'{previous}<span>Pagina {page} di {page_count}</span>{following}</nav>'
    )


def report_html(report, snapshot, page=1):
    trigger = report["trigger"]
    batch = report["batch"]
    query = urlencode({"snapshot": snapshot, "result": trigger["result_id"]})
    download = escape("/report.json?" + query)
    upstream = report["upstream"]
    downstream = report["downstream"]
    coverage = report["coverage_warnings"]
    largest = max(map(len, (upstream, downstream, coverage)))
    page_count = max(1, (largest + PAGE_SIZE - 1) // PAGE_SIZE)
    if page < 1 or page > page_count:
        raise ValueError("Pagina dell’indagine fuori intervallo.")
    start = (page - 1) * PAGE_SIZE
    end = start + PAGE_SIZE
    visible_upstream = upstream[start:end]
    visible_downstream = downstream[start:end]
    warnings = []
    for row in coverage[start:end]:
        note = "Lacuna dichiarata" if row["coverage"] == "known_gap" else "Copertura sconosciuta"
        warnings.append(
            f'<li><strong>{escape(row["batch_id"])}</strong> · {note} '
            f'<span>(batches.csv · record {row["source"]["record"]})</span></li>'
        )
    alert = ""
    if coverage:
        warning_content = "<ul>" + "".join(warnings) + "</ul>" if warnings else "<p>Nessuna segnalazione in questa pagina.</p>"
        alert = (
            '<section class="warning" aria-labelledby="coverage"><h3 id="coverage">'
            f'Copertura delle fonti <span class="count">{len(coverage)}</span></h3>'
            f"{warning_content}</section>"
        )
    rows = evidence_rows(visible_upstream + visible_downstream)
    evidence = ""
    if rows:
        evidence = f"""
            <section class="panel" aria-labelledby="evidence">
              <h3 id="evidence">Record di origine</h3>
              <div class="table-scroll"><table>
                <thead><tr><th scope="col">Fonte</th><th scope="col">Lotto in ingresso</th>
                <th scope="col">Lotto in uscita</th><th scope="col">Operazione</th></tr></thead>
                <tbody>{rows}</tbody>
              </table></div>
            </section>
        """
    return f"""
        <section class="investigation" aria-labelledby="investigation">
          <div class="report-header">
            <div><h2 id="investigation">{escape(trigger["result_id"])}</h2>
              <p>{escape(trigger["analyte"])} · {escape(trigger["value"])}
                {escape(trigger["unit"])} · Fuori specifica</p></div>
            <a class="button secondary" href="{download}">Scarica fascicolo JSON</a>
          </div>
          <section class="origin">
            <h3>Lotto di origine</h3>
            <p><strong>{escape(batch["batch_id"])}</strong> · {escape(batch["material"])}</p>
            <small>results.csv · record {trigger["source"]["record"]}</small>
          </section>
          {alert}
          {pagination_html(query, page, page_count)}
          <div class="paths">
            {batch_list("A monte", visible_upstream, len(upstream))}
            {batch_list("A valle", visible_downstream, len(downstream))}
          </div>
          {evidence}
          <p class="muted note">I percorsi rappresentano la genealogia osservata.
            La valutazione della causa e del rilascio spetta al team qualità.</p>
        </section>
    """


def render_page(snapshots=(), snapshot="", results=(), selected="", report=None, error="", page=1):
    snapshot_options = options_html(
        ((fingerprint, f"Importazione {number} · {fingerprint[:10]}")
         for number, fingerprint in snapshots),
        snapshot,
    )
    result_options = options_html(
        ((row["result_id"], f'{row["result_id"]} · {row["batch_id"]}') for row in results),
        selected,
    )
    content = '<p class="muted">Carica un’importazione SQLite per iniziare.</p>'
    if error:
        content = (
            f'<section class="warning"><p>{escape(error)}</p>'
            '<a href="/">Torna alle indagini</a></section>'
        )
    elif snapshots:
        result_form = '<p class="muted">Nessun risultato fuori specifica in questa importazione.</p>'
        if results:
            result_form = f"""
                <form action="/" method="get">
                  <input type="hidden" name="snapshot" value="{escape(snapshot)}">
                  <div class="field"><label for="result">Risultato fuori specifica</label>
                    <select id="result" name="result" required>
                      <option value="" disabled{"" if selected else " selected"}>Seleziona un risultato</option>
                      {result_options}
                    </select></div>
                  <button type="submit">Apri indagine</button>
                </form>
            """
        content = f"""
            <section class="panel filters" aria-label="Selezione dell’indagine">
              <form action="/" method="get">
                <div class="field"><label for="snapshot">Importazione</label>
                  <select id="snapshot" name="snapshot">{snapshot_options}</select></div>
                <button class="secondary" type="submit">Carica</button>
              </form>
              {result_form}
            </section>
        """
        if report is not None:
            content += report_html(report, snapshot, page)
    return f"""<!DOCTYPE html>
<html lang="it">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>QualityGraph · Indagini qualità</title><link rel="stylesheet" href="/style.css"></head>
<body>
  <header class="site-header"><div class="shell"><a href="/">QualityGraph</a></div></header>
  <main class="shell">
    <h1>Indagini qualità</h1>
    {content}
  </main>
</body>
</html>"""


class BrowserHandler(BaseHTTPRequestHandler):
    def send_content(self, status, body, mime_type, download=False):
        payload = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", f"{mime_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; style-src 'self'; form-action 'self'; "
            "frame-ancestors 'none'; base-uri 'none'",
        )
        self.send_header("X-Content-Type-Options", "nosniff")
        if download:
            self.send_header("Content-Disposition", 'attachment; filename="qualitygraph-report.json"')
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        port = self.server.server_port
        allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
        if port == 80:
            allowed_hosts.update(("127.0.0.1", "localhost"))
        if self.headers.get("Host") not in allowed_hosts:
            self.send_error(400)
            return

        try:
            self.handle_route()
        except ValueError as error:
            self.send_content(400, render_page(error=str(error)), "text/html")
        except sqlite3.Error:
            self.log_error("Could not read the local SQLite database")
            self.send_content(
                500, render_page(error="Impossibile leggere il database locale."), "text/html"
            )

    def handle_route(self):
        url = urlsplit(self.path)
        if url.path == "/style.css":
            self.send_content(200, self.server.stylesheet, "text/css")
            return
        if url.path not in {"/", "/report.json"}:
            self.send_error(404)
            return

        params = parse_qs(url.query, max_num_fields=4)
        snapshot = params.get("snapshot", [""])[0]
        selected = params.get("result", [""])[0]
        if url.path == "/report.json" and not (snapshot and selected):
            raise ValueError("Seleziona un’importazione e un risultato prima di scaricare il fascicolo.")

        snapshots = list_snapshots(self.server.database)
        if not snapshots and not snapshot:
            self.send_content(200, render_page(), "text/html")
            return
        snapshot = snapshot or snapshots[0][1]
        tables, digests = load_snapshot(self.server.database, snapshot)
        report = build_report(tables, digests, selected) if selected else None
        if url.path == "/report.json":
            body = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
            self.send_content(200, body, "application/json", download=True)
            return
        results = [row for row in tables["results.csv"] if row["status"] == "OOS"]
        try:
            page = int(params.get("page", ["1"])[0])
        except ValueError:
            raise ValueError("Numero di pagina non valido.") from None
        html = render_page(snapshots, snapshot, results, selected, report, page=page)
        self.send_content(200, html, "text/html")


class QualityGraphServer(ThreadingHTTPServer):
    def __init__(self, database, port):
        self.database = database.resolve()
        self.stylesheet = Path(__file__).with_name("qualitygraph_web.css").read_text(encoding="utf-8")
        super().__init__(("127.0.0.1", port), BrowserHandler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path, help="SQLite database with saved imports")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        parser.error("--port must be between 0 and 65535")
    try:
        list_snapshots(args.database)
        with QualityGraphServer(args.database, args.port) as server:
            print(f"QualityGraph: http://127.0.0.1:{server.server_port}", flush=True)
            server.serve_forever()
    except KeyboardInterrupt:
        return
    except (OSError, ValueError, sqlite3.Error) as error:
        parser.exit(2, f"qualitygraph-web: {error}\n")


if __name__ == "__main__":
    main()
