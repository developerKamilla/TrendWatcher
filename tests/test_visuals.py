from trendwatcher.visuals import score_ring, factor_bars
from trendwatcher.core import local_card
from trendwatcher.seed import starter_articles


def test_weighted_ring_and_factor_labels():
    card=local_card(starter_articles()[0])
    card['breakdown']=dict(zip(card['breakdown'],[5,4,3,2,1]))
    assert '3.50' in score_ring(card)
    assert '--score:70.0%' in score_ring(card)
    bars=factor_bars(card)
    assert bars.count('class="tw-bar-row"')==5
    assert all(f'{w}%' in bars for w in [30,25,20,15,10])


def test_ring_extremes():
    card=local_card(starter_articles()[0])
    card['breakdown']={k:5 for k in card['breakdown']}
    assert '--score:100.0%' in score_ring(card)
    card['breakdown']={k:1 for k in card['breakdown']}
    assert '--score:20.0%' in score_ring(card)
