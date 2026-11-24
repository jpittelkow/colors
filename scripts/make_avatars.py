"""Draw kidtube's profile characters (ADR 0036) as SVG files in server/app/static/avatars/.

Our own artwork: flat, round, friendly, on a transparent background. The page and the TV put each one on a
coloured circle. Adding a character means adding an entry here (or dropping in one more SVG) and running:

    python scripts/make_avatars.py
"""
from __future__ import annotations

from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "server" / "app" / "static" / "avatars"

INK = "#1d2430"
WHITE = "#ffffff"
BLUSH = '<circle cx="34" cy="62" r="4.5" fill="#ff8a8a" opacity=".5"/><circle cx="66" cy="62" r="4.5" fill="#ff8a8a" opacity=".5"/>'


def eyes(y=52, dx=9, r=3.8, cx=50):
    return (f'<circle cx="{cx - dx}" cy="{y}" r="{r}" fill="{INK}"/><circle cx="{cx + dx}" cy="{y}" r="{r}" fill="{INK}"/>'
            f'<circle cx="{cx - dx + 1.3}" cy="{y - 1.3}" r="{r / 3:.2f}" fill="{WHITE}"/>'
            f'<circle cx="{cx + dx + 1.3}" cy="{y - 1.3}" r="{r / 3:.2f}" fill="{WHITE}"/>')


def smile(y=64, w=6, cx=50):
    return f'<path d="M{cx - w} {y} q{w} {w * 0.8:.1f} {w * 2} 0" stroke="{INK}" stroke-width="2.6" fill="none" stroke-linecap="round"/>'


def face(y=52, mouth=64):
    return eyes(y) + BLUSH + smile(mouth)


CHARACTERS: dict[str, str] = {
    # ---- animals -------------------------------------------------------------------------------------------------
    "fox": (
        '<path d="M22 44 L28 12 L48 30 Z" fill="#f07c2b"/><path d="M78 44 L72 12 L52 30 Z" fill="#f07c2b"/>'
        '<path d="M28 36 L31 20 L41 30 Z" fill="#7a3a12"/><path d="M72 36 L69 20 L59 30 Z" fill="#7a3a12"/>'
        '<circle cx="50" cy="55" r="29" fill="#f07c2b"/>'
        '<path d="M22 58 Q50 92 78 58 Q64 66 50 66 Q36 66 22 58 Z" fill="#fff4e8"/>'
        + eyes(50) + f'<ellipse cx="50" cy="64" rx="4" ry="3" fill="{INK}"/>' + smile(70, 4)
    ),
    "cat": (
        '<path d="M24 46 L26 14 L46 32 Z" fill="#9aa4b1"/><path d="M76 46 L74 14 L54 32 Z" fill="#9aa4b1"/>'
        '<path d="M29 38 L30 22 L40 31 Z" fill="#f4b6c2"/><path d="M71 38 L70 22 L60 31 Z" fill="#f4b6c2"/>'
        '<circle cx="50" cy="56" r="29" fill="#9aa4b1"/>'
        + eyes(52) + '<path d="M46.5 60 h7 l-3.5 4 z" fill="#f4849a"/>'
        f'<path d="M50 64 q-4 4 -8 2 M50 64 q4 4 8 2" stroke="{INK}" stroke-width="2.2" fill="none" stroke-linecap="round"/>'
        f'<path d="M30 60 h-12 M30 65 l-11 3 M70 60 h12 M70 65 l11 3" stroke="{INK}" stroke-width="1.6" stroke-linecap="round" opacity=".6"/>'
    ),
    "dog": (
        '<circle cx="50" cy="54" r="28" fill="#d7a06a"/>'
        '<ellipse cx="22" cy="52" rx="9" ry="19" fill="#8a5630" transform="rotate(12 22 52)"/>'
        '<ellipse cx="78" cy="52" rx="9" ry="19" fill="#8a5630" transform="rotate(-12 78 52)"/>'
        '<ellipse cx="50" cy="66" rx="15" ry="11" fill="#f6dcc0"/>'
        + eyes(50) + f'<ellipse cx="50" cy="61" rx="5" ry="3.6" fill="{INK}"/>'
        '<path d="M46 70 q4 7 8 0 z" fill="#f4849a"/>'
        f'<path d="M44 68 q6 4 12 0" stroke="{INK}" stroke-width="2.2" fill="none" stroke-linecap="round"/>'
    ),
    "bear": (
        '<circle cx="27" cy="30" r="10" fill="#8b5a3c"/><circle cx="73" cy="30" r="10" fill="#8b5a3c"/>'
        '<circle cx="27" cy="30" r="5" fill="#c99872"/><circle cx="73" cy="30" r="5" fill="#c99872"/>'
        '<circle cx="50" cy="55" r="29" fill="#8b5a3c"/>'
        '<ellipse cx="50" cy="66" rx="14" ry="11" fill="#d9b08c"/>'
        + eyes(50) + f'<ellipse cx="50" cy="61" rx="5" ry="3.5" fill="{INK}"/>' + smile(67, 4)
    ),
    "panda": (
        f'<circle cx="27" cy="29" r="10" fill="{INK}"/><circle cx="73" cy="29" r="10" fill="{INK}"/>'
        '<circle cx="50" cy="55" r="29" fill="#ffffff"/>'
        f'<ellipse cx="39" cy="52" rx="7" ry="9" fill="{INK}" transform="rotate(-20 39 52)"/>'
        f'<ellipse cx="61" cy="52" rx="7" ry="9" fill="{INK}" transform="rotate(20 61 52)"/>'
        '<circle cx="40" cy="51" r="2.6" fill="#fff"/><circle cx="60" cy="51" r="2.6" fill="#fff"/>'
        f'<ellipse cx="50" cy="63" rx="4" ry="3" fill="{INK}"/>' + smile(68, 4) + BLUSH
    ),
    "bunny": (
        '<ellipse cx="38" cy="22" rx="8" ry="20" fill="#f3eef0"/><ellipse cx="62" cy="22" rx="8" ry="20" fill="#f3eef0"/>'
        '<ellipse cx="38" cy="24" rx="4" ry="14" fill="#f4b6c2"/><ellipse cx="62" cy="24" rx="4" ry="14" fill="#f4b6c2"/>'
        '<circle cx="50" cy="58" r="27" fill="#f3eef0"/>'
        + eyes(55) + BLUSH.replace('cy="62"', 'cy="64"') + '<path d="M47 62 h6 l-3 3 z" fill="#f4849a"/>'
        f'<path d="M50 65 v3 M50 68 q-3 3 -6 1 M50 68 q3 3 6 1" stroke="{INK}" stroke-width="2" fill="none" stroke-linecap="round"/>'
        '<rect x="47" y="70" width="6" height="5" rx="1" fill="#fff" stroke="#d8cfd3" stroke-width="1"/>'
    ),
    "owl": (
        '<path d="M24 34 L30 16 L40 28 Z" fill="#7b5236"/><path d="M76 34 L70 16 L60 28 Z" fill="#7b5236"/>'
        '<ellipse cx="50" cy="56" rx="29" ry="31" fill="#9a6a45"/>'
        '<ellipse cx="50" cy="70" rx="17" ry="14" fill="#e8cfae"/>'
        '<circle cx="38" cy="47" r="11" fill="#fff"/><circle cx="62" cy="47" r="11" fill="#fff"/>'
        + eyes(47, 12, 5) + '<path d="M46 56 h8 l-4 6 z" fill="#f2a33a"/>'
        '<path d="M42 70 q2 3 4 0 M48 74 q2 3 4 0 M54 70 q2 3 4 0" stroke="#b08860" stroke-width="1.8" fill="none"/>'
    ),
    "frog": (
        '<circle cx="34" cy="34" r="12" fill="#5cbf5c"/><circle cx="66" cy="34" r="12" fill="#5cbf5c"/>'
        '<ellipse cx="50" cy="60" rx="33" ry="25" fill="#5cbf5c"/>'
        '<circle cx="34" cy="33" r="7.5" fill="#fff"/><circle cx="66" cy="33" r="7.5" fill="#fff"/>'
        + eyes(33, 16, 4) + BLUSH.replace('cy="62"', 'cy="60"').replace('cx="34"', 'cx="28"').replace('cx="66"', 'cx="72"')
        + f'<path d="M34 64 q16 12 32 0" stroke="{INK}" stroke-width="2.8" fill="none" stroke-linecap="round"/>'
    ),
    "lion": (
        '<g fill="#d9821f">' + "".join(
            f'<circle cx="{50 + 30 * __import__("math").cos(a * 0.5236):.1f}" cy="{54 + 30 * __import__("math").sin(a * 0.5236):.1f}" r="11"/>'
            for a in range(12)) + '</g>'
        '<circle cx="50" cy="54" r="30" fill="#d9821f"/>'
        '<circle cx="31" cy="32" r="7" fill="#f6c453"/><circle cx="69" cy="32" r="7" fill="#f6c453"/>'
        '<circle cx="50" cy="56" r="23" fill="#f6c453"/>'
        '<ellipse cx="50" cy="66" rx="10" ry="7" fill="#fff0c8"/>'
        + eyes(51, 8, 3.4) + f'<path d="M46 61 h8 l-4 4 z" fill="{INK}"/>' + smile(67, 4)
    ),
    "penguin": (
        '<ellipse cx="50" cy="56" rx="30" ry="32" fill="#2b3440"/>'
        '<path d="M50 40 C34 30 22 44 28 62 C32 76 44 82 50 82 C56 82 68 76 72 62 C78 44 66 30 50 40 Z" fill="#fff"/>'
        + eyes(54, 9, 3.6) + '<path d="M44 61 h12 l-6 6 z" fill="#f2a33a"/>' + BLUSH.replace('cy="62"', 'cy="65"')
    ),
    "whale": (
        '<path d="M14 58 C14 36 34 28 54 30 C76 32 86 46 84 60 C82 74 66 80 48 80 C28 80 14 72 14 58 Z" fill="#4a8fe0"/>'
        '<path d="M84 56 C90 48 96 46 98 42 C96 52 94 58 86 64 Z" fill="#4a8fe0"/>'
        '<path d="M22 66 C34 78 66 78 80 66 C70 74 34 76 22 66 Z" fill="#cfe3fb"/>'
        '<path d="M40 22 q-4 -8 -10 -8 M40 22 q0 -9 4 -12 M40 22 q4 -8 10 -8" stroke="#7fc3f5" stroke-width="3" fill="none" stroke-linecap="round"/>'
        + eyes(54, 10, 3.6, 44) + smile(63, 5, 44)
    ),
    "octopus": (
        '<g fill="#9a6ad8">' + "".join(
            f'<path d="M{x} 62 q{-4 if i % 2 else 4} 14 {2 if i % 2 else -2} 24 q4 2 6 -2 q-4 -12 0 -22 z"/>'
            for i, x in enumerate((24, 34, 44, 56, 66, 74))) + '</g>'
        '<ellipse cx="50" cy="48" rx="28" ry="27" fill="#9a6ad8"/>'
        + eyes(48) + BLUSH.replace('cy="62"', 'cy="57"') + smile(58, 5)
    ),
    # ---- vehicles ------------------------------------------------------------------------------------------------
    "rocket": (
        '<path d="M50 10 C64 22 66 42 64 66 H36 C34 42 36 22 50 10 Z" fill="#f3f5f8"/>'
        '<path d="M50 10 C58 16 62 24 63 32 H37 C38 24 42 16 50 10 Z" fill="#e5484d"/>'
        '<path d="M36 52 L22 70 L36 68 Z" fill="#e5484d"/><path d="M64 52 L78 70 L64 68 Z" fill="#e5484d"/>'
        '<circle cx="50" cy="46" r="8" fill="#5aa9f0" stroke="#9aa4b1" stroke-width="3"/>'
        '<path d="M40 66 Q50 98 60 66 Z" fill="#ffb020"/><path d="M45 66 Q50 86 55 66 Z" fill="#fff1a8"/>'
    ),
    "car": (
        '<path d="M14 62 C14 54 20 50 28 50 L34 36 C36 32 40 30 44 30 H60 C64 30 68 32 70 36 L76 50 C84 50 88 56 88 62 V68 H14 Z" fill="#e5484d"/>'
        '<path d="M38 48 L42 36 H50 V48 Z M54 48 V36 H60 C62 36 64 37 65 39 L68 48 Z" fill="#cfe9ff"/>'
        f'<circle cx="32" cy="70" r="9" fill="{INK}"/><circle cx="70" cy="70" r="9" fill="{INK}"/>'
        '<circle cx="32" cy="70" r="3.5" fill="#d5dbe1"/><circle cx="70" cy="70" r="3.5" fill="#d5dbe1"/>'
        '<rect x="80" y="55" width="7" height="4" rx="2" fill="#ffe08a"/>'
    ),
    "train": (
        '<rect x="20" y="40" width="44" height="30" rx="5" fill="#3f6fd8"/>'
        '<rect x="50" y="26" width="26" height="44" rx="5" fill="#3f6fd8"/>'
        '<rect x="55" y="32" width="16" height="13" rx="3" fill="#cfe9ff"/>'
        '<rect x="26" y="26" width="9" height="16" rx="2" fill="#2b3440"/>'
        '<circle cx="28" cy="18" r="5" fill="#e1e6eb"/><circle cx="36" cy="12" r="4" fill="#e1e6eb"/>'
        '<path d="M76 62 L86 70 H76 Z" fill="#e5484d"/>'
        f'<circle cx="32" cy="72" r="8" fill="{INK}"/><circle cx="52" cy="72" r="8" fill="{INK}"/><circle cx="68" cy="72" r="8" fill="{INK}"/>'
        '<circle cx="32" cy="72" r="3" fill="#ffc233"/><circle cx="52" cy="72" r="3" fill="#ffc233"/><circle cx="68" cy="72" r="3" fill="#ffc233"/>'
    ),
    "digger": (
        f'<rect x="14" y="66" width="52" height="14" rx="7" fill="{INK}"/>'
        '<circle cx="22" cy="73" r="4" fill="#6b7682"/><circle cx="40" cy="73" r="4" fill="#6b7682"/><circle cx="58" cy="73" r="4" fill="#6b7682"/>'
        '<rect x="18" y="46" width="44" height="20" rx="4" fill="#ffc233"/>'
        '<path d="M24 46 V30 C24 28 26 26 28 26 H44 C46 26 48 28 48 30 V46 Z" fill="#ffc233"/>'
        '<rect x="29" y="31" width="14" height="12" rx="2" fill="#cfe9ff"/>'
        '<path d="M58 50 L76 30 L82 34 L66 54 Z" fill="#f0a500"/>'
        '<path d="M76 30 L88 52 L84 54 L74 36 Z" fill="#f0a500"/>'
        f'<path d="M80 50 H94 L90 64 H78 Z" fill="#6b7682"/>'
    ),
    "boat": (
        '<path d="M50 14 V58" stroke="#8a5630" stroke-width="3"/>'
        '<path d="M52 16 L78 54 H52 Z" fill="#ffffff"/><path d="M48 24 L26 54 H48 Z" fill="#ffc233"/>'
        '<path d="M16 60 H84 L74 78 H26 Z" fill="#e5484d"/>'
        '<path d="M8 84 q7 -6 14 0 t14 0 t14 0 t14 0 t14 0 t14 0" stroke="#5aa9f0" stroke-width="4" fill="none" stroke-linecap="round"/>'
    ),
    "plane": (
        '<path d="M14 52 C14 46 20 44 28 44 H74 C84 44 92 48 92 52 C92 56 84 60 74 60 H28 C20 60 14 58 14 52 Z" fill="#f3f5f8"/>'
        '<path d="M44 46 L60 16 H68 L60 46 Z" fill="#3f6fd8"/><path d="M44 58 L60 88 H68 L60 58 Z" fill="#3f6fd8"/>'
        '<path d="M16 50 L10 32 H18 L28 46 Z" fill="#e5484d"/>'
        '<circle cx="80" cy="50" r="3" fill="#5aa9f0"/><circle cx="70" cy="50" r="3" fill="#5aa9f0"/><circle cx="36" cy="50" r="3" fill="#5aa9f0"/>'
    ),
    # ---- food ----------------------------------------------------------------------------------------------------
    "apple": (
        '<path d="M50 30 C40 22 18 24 18 50 C18 72 34 88 50 82 C66 88 82 72 82 50 C82 24 60 22 50 30 Z" fill="#e5484d"/>'
        '<path d="M50 30 C50 22 52 16 56 12" stroke="#7a4a1f" stroke-width="3.5" fill="none" stroke-linecap="round"/>'
        '<path d="M54 22 C62 12 74 14 76 18 C70 26 60 26 54 22 Z" fill="#5cbf5c"/>'
        + face(54, 64)
    ),
    "cupcake": (
        '<path d="M26 56 H74 L68 86 H32 Z" fill="#5aa9f0"/>'
        '<path d="M36 56 L38 86 M50 56 V86 M64 56 L62 86" stroke="#3f86d0" stroke-width="2"/>'
        '<path d="M22 58 C16 46 30 36 38 40 C38 26 62 24 64 38 C74 34 86 46 78 58 Z" fill="#f7b6cf"/>'
        '<circle cx="50" cy="24" r="6" fill="#e5484d"/>'
        '<rect x="34" y="44" width="5" height="2.5" rx="1" fill="#ffc233" transform="rotate(30 36 45)"/>'
        '<rect x="60" y="46" width="5" height="2.5" rx="1" fill="#5cbf5c" transform="rotate(-25 62 47)"/>'
        + eyes(68, 8, 3.2) + smile(76, 4)
    ),
    "watermelon": (
        '<path d="M12 40 H88 C88 64 72 82 50 82 C28 82 12 64 12 40 Z" fill="#3aa35b"/>'
        '<path d="M17 40 H83 C83 60 69 76 50 76 C31 76 17 60 17 40 Z" fill="#f05d6b"/>'
        + "".join(f'<ellipse cx="{x}" cy="{y}" rx="1.8" ry="3" fill="{INK}"/>' for x, y in ((30, 52), (70, 52), (40, 66), (60, 66), (50, 70)))
        + eyes(50, 9, 3.4) + smile(58, 5)
    ),
    # ---- sky and space -------------------------------------------------------------------------------------------
    "star": (
        '<path d="M50 10 L61 36 L89 38 L67 56 L74 84 L50 69 L26 84 L33 56 L11 38 L39 36 Z" fill="#ffc233" stroke="#f0a500" stroke-width="3" stroke-linejoin="round"/>'
        + eyes(50, 8, 3.4) + BLUSH.replace('cy="62"', 'cy="57"').replace('cx="34"', 'cx="37"').replace('cx="66"', 'cx="63"')
        + smile(58, 4)
    ),
    "moon": (
        '<path d="M60 12 C36 12 18 30 18 52 C18 74 36 90 58 90 C70 90 80 84 86 76 C62 78 44 62 44 42 C44 28 50 18 60 12 Z" fill="#ffe08a"/>'
        '<circle cx="34" cy="38" r="3" fill="#f0c95a"/><circle cx="40" cy="74" r="4" fill="#f0c95a"/>'
        f'<path d="M31 54 q3 -3 6 0" stroke="{INK}" stroke-width="2.4" fill="none" stroke-linecap="round"/>'
        f'<path d="M45 66 q4 3 8 0" stroke="{INK}" stroke-width="2.4" fill="none" stroke-linecap="round"/>'
        '<circle cx="30" cy="62" r="4" fill="#ff8a8a" opacity=".5"/>'
        '<path d="M76 24 l2 5 l5 2 l-5 2 l-2 5 l-2 -5 l-5 -2 l5 -2 z" fill="#ffffff"/>'
    ),
    "planet": (
        '<ellipse cx="50" cy="54" rx="44" ry="12" fill="none" stroke="#f0a500" stroke-width="5" transform="rotate(-18 50 54)"/>'
        '<circle cx="50" cy="52" r="26" fill="#f07c6b"/>'
        '<path d="M27 42 C40 47 60 38 74 44" stroke="#e05a4a" stroke-width="4" fill="none" stroke-linecap="round"/>'
        + eyes(54, 8, 3.4) + smile(62, 4)
        + '<path d="M6 54 A44 12 0 0 0 94 54" fill="none" stroke="#f0a500" stroke-width="5" stroke-linecap="round" transform="rotate(-18 50 54)"/>'
    ),
}


def svg(body: str, name: str) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" role="img" aria-label="{name}">'
            f"{body}</svg>\n")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, body in CHARACTERS.items():
        (OUT / f"{name}.svg").write_text(svg(body, name), encoding="utf-8")
    print(f"wrote {len(CHARACTERS)} characters to {OUT}")


if __name__ == "__main__":
    main()
