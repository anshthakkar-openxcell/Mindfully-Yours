"""Exports each diagram as SVG + a 2x PNG. Headless Chrome reserves part of the window height for its own UI,
so the page is captured taller than needed and the blank bottom is trimmed back to the SVG's real height."""
import pathlib
import subprocess

from PIL import Image

from diagrams import kb_build, part_a, part_b, rds_vector, system

OUT = pathlib.Path(__file__).parent.parent / "diagrams"
OUT.mkdir(exist_ok=True)
ITEMS = [("1_System_Overview", system(), 614), ("2_RDS_and_Vector_Database", rds_vector(6440), 565),
         ("3_Knowledge_Base_Build", kb_build(5230, 6440), 579), ("4a_Reply_Flow_Part_A_Message_to_Safety_Check", part_a(), 654),
         ("4b_Reply_Flow_Part_B_Choose_and_Deliver", part_b(), 746)]
for name, svg, h in ITEMS:
    t = svg.render().replace('width="100%" preserveAspectRatio="xMidYMid meet"', f'width="1110" height="{h}" preserveAspectRatio="xMidYMid meet"')
    (OUT / f"{name}.svg").write_text(t)
    html = OUT / f"_{name}.html"
    html.write_text(f'<!doctype html><body style="margin:0;background:#fff">{t}</body>')
    png = (OUT / f"{name}.png").resolve()
    subprocess.run(["google-chrome", "--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=2",
                    f"--screenshot={png}", f"--window-size=1110,{h + 200}", f"file://{html.resolve()}"], capture_output=True, check=True)
    html.unlink()
    img = Image.open(png)
    img.crop((0, 0, 1110 * 2, h * 2)).save(png)
    print(name, img.size, "->", (1110 * 2, h * 2))
