"""Reproducible synthetic parcel evidence; no personal data or real parcel claim."""
import hashlib
import random
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageEnhance

ROOT=Path(__file__).resolve().parent

def generate_assets(directory):
    directory=Path(directory);directory.mkdir(exist_ok=True)
    background=Image.open(ROOT/'assets/synthetic-parcel.png').convert('RGB').resize((800,600))
    font_path=Path('C:/Windows/Fonts/arial.ttf')
    font=ImageFont.truetype(str(font_path),22) if font_path.exists() else ImageFont.load_default(size=22)
    for n in range(60):
        sid='PV-DEMO-001' if n==0 else f'PV-SHIP-{n+1:03d}'
        for stage in ('handoff_submitted','pod_submitted'):
            destination=directory/f'v4_{sid}_{stage}.jpg'
            if destination.exists():continue
            rng=random.Random(sid+stage)
            # Controlled color, viewpoint and barcode variation; equality is never
            # inferred from these labels. Case A explicitly reuses one file.
            image=ImageEnhance.Color(background).enhance(.65+rng.random()*.7)
            image=image.rotate(rng.uniform(-5,5),resample=Image.Resampling.BICUBIC,expand=False,fillcolor=(222,220,210))
            draw=ImageDraw.Draw(image)
            x,y=500,90
            draw.rectangle((x,y,x+260,y+210),fill=(245,241,226),outline=(65,70,62),width=2)
            draw.text((x+12,y+12),'SYNTHETIC PARCEL',fill=(35,45,37),font=font)
            draw.text((x+12,y+44),sid,fill=(35,45,37),font=font)
            for i in range(75):
                if rng.random()>.45:draw.rectangle((x+12+i*3,y+85,x+13+i*3,y+145),fill=(25,35,28))
            draw.text((x+12,y+163),'Handed over' if stage=='handoff_submitted' else 'Delivery record',fill=(35,45,37),font=font)
            draw.rectangle((0,554,800,600),fill=(242,242,234))
            draw.text((18,562),'Illustrative synthetic evidence — contents not verified',fill=(40,55,46),font=font)
            image.save(destination,quality=88)
    source=directory/'v4_PV-SHIP-011_handoff_submitted.jpg'
    near=directory/'v4_PV-SHIP-011_near_delivery.jpg'
    if not near.exists():ImageEnhance.Brightness(Image.open(source)).enhance(.98).save(near,quality=88)

if __name__=='__main__':generate_assets(ROOT/'fixtures')
