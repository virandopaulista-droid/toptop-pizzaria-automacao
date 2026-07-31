#!/usr/bin/env python3
"""Resolves a filename inside the shared "AGENTE - STORIES" Drive folder
(TopTop Pizzaria) to a public direct-download URL, without needing Drive API
credentials.

How it works: the folder's public embed view (embeddedfolderview) exposes
each file as an <a href="https://drive.google.com/file/d/<ID>/view..."> --
we scrape that HTML for filename->file_id, then build the direct-download
link (https://drive.google.com/uc?export=download&id=<ID>), which redirects
to a stable https://drive.usercontent.google.com/download?... URL. Same
technique already proven working for the Bernardino Restaurante automation.

Usage: resolve_drive_url.py <filename> [folder_id]
  folder_id defaults to the "AGENTE - STORIES" folder; pass a different
  publicly-shared folder's ID to resolve files there instead.
Prints the direct-download URL, or exits 1 with an error if not found.
"""
import re
import sys
import urllib.request

DEFAULT_FOLDER_ID = "1RNjSyqeRhufdJtNAreanm3cPpnDP-RPw"  # AGENTE - STORIES (TopTop Pizzaria)

PATTERN = re.compile(
    r'href="https://drive\.google\.com/file/d/([a-zA-Z0-9_-]+)/view[^"]*"[^>]*>.*?'
    r'flip-entry-title">([^<]+)</div>'
)


def fetch_id_map(folder_id):
    embed_url = f"https://drive.google.com/embeddedfolderview?id={folder_id}#list"
    req = urllib.request.Request(embed_url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp:
        html = resp.read().decode("utf-8", errors="replace")
    return {name: file_id for file_id, name in PATTERN.findall(html)}


def main():
    if len(sys.argv) not in (2, 3):
        print("Uso: resolve_drive_url.py <filename> [folder_id]", file=sys.stderr)
        raise SystemExit(1)
    filename = sys.argv[1]
    folder_id = sys.argv[2] if len(sys.argv) == 3 else DEFAULT_FOLDER_ID
    id_map = fetch_id_map(folder_id)
    file_id = id_map.get(filename)
    if not file_id:
        print(f"ERRO: '{filename}' nao encontrado no embed da pasta ({len(id_map)} arquivos vistos).", file=sys.stderr)
        raise SystemExit(1)
    print(f"https://drive.google.com/uc?export=download&id={file_id}")


if __name__ == "__main__":
    main()
