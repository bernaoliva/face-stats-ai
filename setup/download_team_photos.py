"""Download player photos from official team websites (confirmed working sources).

Downloads to extra_photos/ for use with enrich_db.py.

Usage:
    python -m setup.download_team_photos [--output extra_photos/]
"""
from __future__ import annotations

import argparse
import logging
import re
import time
import urllib.request
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# ============================================================
# Confirmed player data from official team websites (2026)
# ============================================================

FLAMENGO = [
    ("Dyogo Alves", "https://images.flamengo.com.br/public/images/players/1/1770040134.png"),
    ("Rossi", "https://images.flamengo.com.br/public/images/players/1/1770040178.png"),
    ("Andrew", "https://images.flamengo.com.br/public/images/players/1/1769804692.png"),
    ("Leo Pereira", "https://images.flamengo.com.br/public/images/players/2/1770039090.png"),
    ("Leo Ortiz", "https://images.flamengo.com.br/public/images/players/2/1769718636.png"),
    ("Danilo", "https://images.flamengo.com.br/public/images/players/2/1770040043.png"),
    ("Joao Victor", "https://images.flamengo.com.br/public/images/players/2/1770055299.png"),
    ("Vitao", "https://images.flamengo.com.br/public/images/players/2/1770040087.png"),
    ("Varela", "https://images.flamengo.com.br/public/images/players/3/1770039941.png"),
    ("Emerson Royal", "https://images.flamengo.com.br/public/images/players/3/1770039971.png"),
    ("Ayrton Lucas", "https://images.flamengo.com.br/public/images/players/4/1770039857.png"),
    ("Alex Sandro", "https://images.flamengo.com.br/public/images/players/4/1770039887.png"),
    ("Evertton Araujo", "https://images.flamengo.com.br/public/images/players/5/1770039235.png"),
    ("Erick", "https://images.flamengo.com.br/public/images/players/5/1769717954.png"),
    ("Jorginho", "https://images.flamengo.com.br/public/images/players/5/1770039810.png"),
    ("Arrascaeta", "https://images.flamengo.com.br/public/images/players/6/1770039345.png"),
    ("De La Cruz", "https://images.flamengo.com.br/public/images/players/6/1770040247.png"),
    ("Saul", "https://images.flamengo.com.br/public/images/players/6/1769807711.png"),
    ("Carrascal", "https://images.flamengo.com.br/public/images/players/6/1770039296.png"),
    ("Paqueta", "https://images.flamengo.com.br/public/images/players/6/1769807589.png"),
    ("Bruno Henrique", "https://images.flamengo.com.br/public/images/players/7/1770039577.png"),
    ("Pedro", "https://images.flamengo.com.br/public/images/players/7/1770039624.png"),
    ("Everton", "https://images.flamengo.com.br/public/images/players/7/1770039464.png"),
    ("Luiz Araujo", "https://images.flamengo.com.br/public/images/players/7/1769717598.png"),
    ("Gonzalo Plata", "https://images.flamengo.com.br/public/images/players/7/1770039412.png"),
    ("Wallace Yan", "https://images.flamengo.com.br/public/images/players/7/1770054862.png"),
    ("Savio Lino", "https://images.flamengo.com.br/public/images/players/7/1770039665.png"),
]

SAO_PAULO = [
    ("Toloi", "https://cdn.saopaulofc.net/2026/02/toloi.png"),
    ("Doria", "https://cdn.saopaulofc.net/2026/02/doria.png"),
    ("Arboleda", "https://cdn.saopaulofc.net/2026/02/arboleda.png"),
    ("Lucas", "https://cdn.saopaulofc.net/2026/02/lucas.png"),
    ("Marcos Antonio", "https://cdn.saopaulofc.net/2026/02/marcos-antonio.png"),
    ("Calleri", "https://cdn.saopaulofc.net/2026/02/calleri.png"),
    ("Luciano", "https://cdn.saopaulofc.net/2026/02/luciano.png"),
    ("Ferreira", "https://cdn.saopaulofc.net/2026/02/ferreira.png"),
    ("Enzo", "https://cdn.saopaulofc.net/2026/02/enzo.png"),
    ("Tapia", "https://cdn.saopaulofc.net/2026/02/tapia-vale.png"),
    ("Bobadilla", "https://cdn.saopaulofc.net/2026/02/d-bobadilla.png"),
    ("Andre Silva", "https://cdn.saopaulofc.net/2026/02/andre-silva.png"),
    ("Wendell", "https://cdn.saopaulofc.net/2026/02/wendell.png"),
    ("Cedric", "https://cdn.saopaulofc.net/2026/02/cedric.png"),
    ("Rafael", "https://cdn.saopaulofc.net/2026/02/rafael.png"),
    ("Alisson", "https://cdn.saopaulofc.net/2026/02/alisson.png"),
    ("Alan Franco", "https://cdn.saopaulofc.net/2026/02/alan-franco.png"),
    ("Pablo Maia", "https://cdn.saopaulofc.net/2026/02/pablo-maia.png"),
    ("Negrucci", "https://cdn.saopaulofc.net/2026/02/negrucci.png"),
    ("Coronel", "https://cdn.saopaulofc.net/2026/02/coronel.png"),
    ("Ferraresi", "https://cdn.saopaulofc.net/2026/02/ferraresi.png"),
    ("Luan", "https://cdn.saopaulofc.net/2026/02/luan.png"),
    ("Sabino", "https://cdn.saopaulofc.net/2026/02/sabino.png"),
    ("Hugo", "https://cdn.saopaulofc.net/2026/02/hugo.png"),
    ("Maik", "https://cdn.saopaulofc.net/2026/02/maik.png"),
    ("Lucca", "https://cdn.saopaulofc.net/2026/02/lucca.png"),
    ("Ryan Francisco", "https://cdn.saopaulofc.net/2026/02/ryan.png"),
    ("Young", "https://cdn.saopaulofc.net/2026/02/young.png"),
    ("Felipe Preis", "https://cdn.saopaulofc.net/2026/02/felipe-preis.png"),
    ("Danielzinho", "https://cdn.saopaulofc.net/2026/02/danielzinho.png"),
]

CORINTHIANS = [
    ("Felipe Longo", "https://static.corinthians.com.br/uploads/174602515030588d486e7f64ccfa2279872230ab5e_jogador.png"),
    ("Hugo Souza", "https://static.corinthians.com.br/uploads/17460249976f3b2755d224d99e8f36a3769081a0c4_jogador.png"),
    ("Kaue", "https://static.corinthians.com.br/uploads/177090814516f102c8aeb8c4b40d12b7fd6ddce0a6_jogador.png"),
    ("Matheus Donelli", "https://static.corinthians.com.br/uploads/1746024677616d2379d061ca5741d935e17ea0fb4e_jogador.png"),
    ("Andre Ramalho", "https://static.corinthians.com.br/uploads/17460237851bf90d4a02ed90d2a2abc1acd236f1e1_jogador.png"),
    ("Gabriel Paulista", "https://static.corinthians.com.br/uploads/176840182873e4030d6ed947bec8dbf16544bdc3d1_jogador.png"),
    ("Gustavo Henrique", "https://static.corinthians.com.br/uploads/1746024875295917b50b77e1a1539c9ad57a7a5b80_jogador.png"),
    ("Joao Pedro", "https://static.corinthians.com.br/uploads/1746025475cef1c3780f89c8f680755acb33be3f59_jogador.png"),
    ("Fabrizio Angileri", "https://static.corinthians.com.br/uploads/17460241684f74897fa0265ad89cfa30735a74dbab_jogador.png"),
    ("Hugo", "https://static.corinthians.com.br/uploads/1746024956f8205b8766c8002f073b40955d992a8e_jogador.png"),
    ("Matheuzinho", "https://static.corinthians.com.br/uploads/17460252157791624d60ee279dcd406d157a40cc48_jogador.png"),
    ("Matheus Bidu", "https://static.corinthians.com.br/uploads/1746024344b751c6fabf80fb7b15a37db83792b3ca_jogador.png"),
    ("Andre Carrillo", "https://static.corinthians.com.br/uploads/1746024400fcf5eb5b11d3adc30c7258a4907695b3_jogador.png"),
    ("Breno Bidon", "https://static.corinthians.com.br/uploads/17460242974c9178c498c5b0dd9d15d1b92bfda1e3_jogador.png"),
    ("Charles", "https://static.corinthians.com.br/uploads/17460246091dcfb616a81ab903e262a8df840d1c55_jogador.png"),
    ("Raniele", "https://static.corinthians.com.br/uploads/174602536121e5742c1276d3c9f3b8533f68862bf3_jogador.png"),
    ("Rodrigo Garro", "https://static.corinthians.com.br/uploads/174602474203faf90b8ef5ed5b04ed826fdade3f2f_jogador.png"),
    ("Memphis", "https://static.corinthians.com.br/uploads/17460253095eb4ceaac5b5793f989be1ec24dbcfe2_jogador.png"),
    ("Pedro Raul", "https://static.corinthians.com.br/uploads/1768228514ae389c5ee4457ab6e70ee6d1539adbc3_jogador.png"),
    ("Yuri Alberto", "https://static.corinthians.com.br/uploads/1746025501b5ca6edba1907b34c8f6a85b3ac24eeb_jogador.png"),
    ("Kayke", "https://static.corinthians.com.br/uploads/17460250576d03a7143104797ceb72a8c354f5ea41_jogador.png"),
    ("Lingard", "https://static.corinthians.com.br/uploads/1772721025f19d68211b41e2a2bd75e76e5ffe8e3e_jogador.png"),
    ("Matheus Pereira", "https://static.corinthians.com.br/uploads/176859931944bb14c1b0cb35a90cfba21ebe78ff59_jogador.png"),
]

BOTAFOGO = [
    ("Gatito Fernandez", "https://static.botafogo.com.br/upload/jogador/82256fd11b054de7b96114cbbfc4bd91.png"),
    ("Leonardo Linck", "https://static.botafogo.com.br/upload/jogador/4d0be16b65d14c3c96ad3208b18f6147.png"),
    ("Neto", "https://static.botafogo.com.br/upload/jogador/1f3358a8b77d4a2e8464a2223ac2b426.png"),
    ("Raul", "https://static.botafogo.com.br/upload/jogador/029a9701f9ec4aa38c34f82d8183200e.png"),
    ("Alex Telles", "https://static.botafogo.com.br/upload/jogador/e8e936ef325c4c519c1e9a68b059dbf3.png"),
    ("Alexander Barboza", "https://static.botafogo.com.br/upload/jogador/94a4221a5242496ea1826ee60f91c809.png"),
    ("Bastos", "https://static.botafogo.com.br/upload/jogador/64d2313a800c4e2699740905e9f74c25.png"),
    ("Ferraresi", "https://static.botafogo.com.br/upload/jogador/4f01bf0038f744dcb5d477b6b2034e7f.png"),
    ("Jhoan Hernandez", "https://static.botafogo.com.br/upload/jogador/f3413ffe587045a8964ca8c0f060af5f.png"),
    ("Carlos Eduardo", "https://static.botafogo.com.br/upload/jogador/49c70e13f6cc4e9caaeaac5867ad4836.png"),
    ("Kaio Pantaleao", "https://static.botafogo.com.br/upload/jogador/648f048dbf1449509e16a3f05b31a707.png"),
    ("Fernando Marcal", "https://static.botafogo.com.br/upload/jogador/79cd4dc3df6b4da48f454790a8549900.png"),
    ("Mateo Ponte", "https://static.botafogo.com.br/upload/jogador/33e100185e1a4dfaba70a0bc82d992c7.png"),
    ("Vitinho", "https://static.botafogo.com.br/upload/jogador/126394156d6d4f3ab94cbe2154458e4d.png"),
    ("Ythallo", "https://static.botafogo.com.br/upload/jogador/43688451dca54b42a533c5b3ab968e44.png"),
    ("Allan", "https://static.botafogo.com.br/upload/jogador/4e31fa011b7347f6a5fb289d3d1d52a8.png"),
    ("Alvaro Montoro", "https://static.botafogo.com.br/upload/jogador/964d0a899724435f86a39f6d40ce3bdf.png"),
    ("Cristian Medina", "https://static.botafogo.com.br/upload/jogador/3605c47047354b4cb2a0b86e9c38c3b4.png"),
    ("Danilo", "https://static.botafogo.com.br/upload/jogador/828f2d653cfb41ae83ea71ce5dc97263.png"),
    ("Edenilson", "https://static.botafogo.com.br/upload/jogador/230f884e0d9343b984e0d198544f9300.png"),
    ("Victor Hugo", "https://static.botafogo.com.br/upload/jogador/a636f32dfa0746b5aedc60709b57a4d0.png"),
    ("Barrera", "https://static.botafogo.com.br/upload/jogador/fdb81fa81ee844b29abf731b885b6df2.png"),
    ("Junior Santos", "https://static.botafogo.com.br/upload/jogador/766b049efc1d40a38ecd5d55552ddff4.png"),
    ("Savarino", "https://static.botafogo.com.br/upload/jogador/b956d46d8d0d407593eeeccc1e28c5bd.png"),
    ("Arthur Cabral", "https://static.botafogo.com.br/upload/jogador/75c906c1b0054d55aa8ff9e357b8b177.png"),
    ("Artur Victor", "https://static.botafogo.com.br/upload/jogador/cd3a40fbc6d647a5a95af572be7a52e9.png"),
    ("Christopher", "https://static.botafogo.com.br/upload/jogador/fcd70699e9ac41258b491b47b6a6957a.png"),
    ("Carlos Correa", "https://static.botafogo.com.br/upload/jogador/a7cb4765bb8545b1ad343c3ef3ac7c00.png"),
    ("Tiquinho Soares", "https://static.botafogo.com.br/upload/jogador/63ca90afa74f4a6caa91eac1737a9c2f.png"),
    ("Jose Barrea", "https://static.botafogo.com.br/upload/jogador/d8565b77dab045f6aa494fa0a5ab1b7a.png"),
    ("Lucas Villalba", "https://static.botafogo.com.br/upload/jogador/e05e1c27138f43f6af52ccad779a7ba8.png"),
    ("Matheus Martins", "https://static.botafogo.com.br/upload/jogador/94337f14c5904f788ade06b4bf71108b.png"),
    ("Nathan", "https://static.botafogo.com.br/upload/jogador/2bcc23a3624649efbe283ba924b139cd.png"),
]

ALL_TEAMS = {
    "Flamengo": FLAMENGO,
    "Sao Paulo": SAO_PAULO,
    "Corinthians": CORINTHIANS,
    "Botafogo": BOTAFOGO,
}


def _download(url: str, path: Path) -> bool:
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
        if len(data) < 500:
            return False
        path.write_bytes(data)
        return True
    except Exception as e:
        logger.warning("Failed: %s -> %s", url, e)
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Download player photos from official team websites")
    parser.add_argument("--output", default="extra_photos", help="Output folder")
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(exist_ok=True)

    total = sum(len(players) for players in ALL_TEAMS.values())
    print(f"Downloading {total} player photos from {len(ALL_TEAMS)} teams\n")

    downloaded = 0
    skipped = 0
    failed = 0

    for team, players in ALL_TEAMS.items():
        print(f"\n{team} ({len(players)} jogadores):")
        for name, url in players:
            safe_name = re.sub(r'[<>:"/\\|?*]', '_', name)
            ext = ".png" if ".png" in url.lower() else ".jpg"
            path = output_dir / f"{safe_name}{ext}"

            if path.exists():
                skipped += 1
                continue

            if _download(url, path):
                downloaded += 1
                print(f"  OK: {name}")
            else:
                failed += 1
                print(f"  FAIL: {name}")
            time.sleep(0.15)

    print(f"\n{'='*40}")
    print(f"Downloaded: {downloaded}")
    print(f"Skipped (existing): {skipped}")
    print(f"Failed: {failed}")
    print(f"Total in {args.output}/: {downloaded + skipped}")


if __name__ == "__main__":
    main()
