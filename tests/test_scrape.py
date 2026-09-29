from bs4 import BeautifulSoup

from framecoach.scrape import parse_character_page, parse_stats_page

CHARACTER_HTML = """
<h1>Ryu</h1>
<div id="contentcontainer">
  <div class="moves">
    <div class="movecontainer">
      <div class="movename">Standing Light Punch</div>
      <div class="startup">4</div>
      <div class="onblock">-1</div>
    </div>
  </div>
</div>
"""

STATS_HTML = """
<div id="health"><table class="statstable">
  <thead><tr><th>Character</th><th>Health</th></tr></thead>
  <tbody><tr><td>Ryu</td><td>10,000</td></tr><tr><td>Akuma</td><td>9,000</td></tr></tbody>
</table></div>
"""


def test_parse_character_page():
    data = parse_character_page(BeautifulSoup(CHARACTER_HTML, "html.parser"), "ryu")
    assert data["character"] == "Ryu"
    move = data["moves"][0]
    assert move["move"] == "Standing Light Punch" and move["startup"] == "4" and move["onblock"] == "-1"
    assert move["recovery"] == ""


def test_parse_stats_page():
    stats = parse_stats_page(BeautifulSoup(STATS_HTML, "html.parser"))
    assert stats == {"Ryu": {"Health": "10,000"}, "Akuma": {"Health": "9,000"}}
