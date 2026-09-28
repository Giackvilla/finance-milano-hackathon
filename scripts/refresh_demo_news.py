#!/usr/bin/env python3
"""Replace news type on the demo cards with the Gemini classifier.

Keeps scheduled and headline_reports_move from the keyword rules, because the
verdict text already uses those. Does not regenerate the Gemini sentence.
One classification per article (Italian), written to both language folders.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from build_card import news_block_for  # noqa: E402
from classify import classify  # noqa: E402
from classify_gemini import fetch_article, fetch_instruments  # noqa: E402

FOLDERS = [ROOT / "data" / "cards_gemini_en", ROOT / "data" / "cards_gemini_it"]


def ids_from(folder: Path):
    index = json.loads((folder / "index.json").read_text())
    return [c["content_id"] for c in index["cards"]]


def main():
    ids = ids_from(FOLDERS[0])
    instruments = fetch_instruments()
    for i, cid in enumerate(ids, 1):
        article = fetch_article(cid)
        kw = classify(article.get("titolo") or "", article.get("body") or "")
        sample = json.loads((FOLDERS[0] / f"{cid}.json").read_text())
        block = news_block_for(
            article.get("titolo") or "",
            article.get("body") or "",
            article,
            kw,
            instruments=instruments,
            use_gemini_news=True,
            lang="it",
            card_code=(sample.get("instrument") or {}).get("cod_azione"),
        )
        for folder in FOLDERS:
            path = folder / f"{cid}.json"
            card = json.loads(path.read_text())
            card["news"] = block
            path.write_text(json.dumps(card, ensure_ascii=False, indent=2) + "\n")
            index_path = folder / "index.json"
            index = json.loads(index_path.read_text())
            for entry in index["cards"]:
                if entry["content_id"] == cid:
                    entry["news_type"] = block["news_type"]
                    entry["classifier"] = block["classifier"]
            index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n")
        print(
            f"[{i}/{len(ids)}] {sample['instrument']['des_azione']}: "
            f"{kw['news_type']} -> {block['news_type']} "
            f"agrees={block['instrument_agrees']} gemini={block['gemini_des_azione']}",
            flush=True,
        )


if __name__ == "__main__":
    main()
