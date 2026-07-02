# photo-to-resin

Zamień zwykłe zdjęcie w **litofan** — cienką płytkę żywicy, na której obraz
pojawia się dopiero pod światło. Na wejściu JPG/PNG, na wyjściu binarny STL
gotowy do slicera drukarki żywicznej (Lychee, Chitubox).

![Litofan wygenerowany tym narzędziem](site/assets/litofan-podswietlony.png)

## Jak to działa

1. **Jasność staje się grubością** — każdy piksel dostaje grubość żywicy:
   ciemne miejsca grubsze (przepuszczają mniej światła), jasne cieńsze.
2. **Mapa wysokości staje się bryłą** — szczelna siatka: rzeźbiona
   powierzchnia, płaski spód, domknięte ścianki, opcjonalna ramka.
3. **Bryła staje się plikiem STL** — binarny STL z wymiarami w milimetrach.

## Instalacja

```bash
git clone https://github.com/arturskowronski/photo-to-resin
cd photo-to-resin
pip install -e .            # sama biblioteka + CLI
pip install -e ".[notebook]"  # z interfejsem dla Jupytera
```

## Interfejs w Jupyterze

Panel z suwakami, podglądem podświetlenia na żywo (symulacja transmisji
światła) i szacunkiem rozmiaru pliku przed generowaniem:

```bash
jupyter lab notebooks/interfejs.ipynb
```

albo w dowolnym notebooku:

```python
from photo_to_resin.notebook import launch
launch()
```

## Z wiersza poleceń

```bash
photo-to-resin zdjecie.jpg -o litofan.stl --width 80 --resolution 4
```

## Z kodu

```python
from photo_to_resin import LithophaneParams, photo_to_stl

params = LithophaneParams(width_mm=80, min_thickness_mm=0.6, max_thickness_mm=2.8)
photo_to_stl("zdjecie.jpg", "litofan.stl", params)
```

## Strona

Statyczna strona reklamowa leży w `site/` — grafiki na niej są prawdziwym
outputem biblioteki (`scripts/make_site_assets.py`). Podgląd lokalnie:

```bash
python3 -m http.server -d site 8741
```

## Wskazówki do druku

- Żywica mleczna lub jasnoszara daje najlepszy kontrast; czarna nie przepuszcza światła.
- Grubość 0.6–2.8 mm to sprawdzony zakres; poniżej 0.4 mm robi się kruche.
- Rozdzielczość 4 px/mm wystarcza — drukarka i tak wygładzi detal, a plik nie puchnie.
- Drukuj płytkę pionowo lub pod kątem, gładką stroną (spodem) do LCD.

## Testy

```bash
python3 tests/test_core.py
```

Testy sprawdzają m.in. szczelność siatki (każda krawędź w dokładnie dwóch
trójkątach) i zgodność objętości bryły z całką z mapy wysokości.

## Licencja

MIT
