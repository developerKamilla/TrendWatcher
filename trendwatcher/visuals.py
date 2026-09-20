"""Small, data-driven HTML components. No external assets or network calls."""
from html import escape
from .core import WEIGHTS, FACTOR_NAMES, compute_score


def score_ring(card):
    value = compute_score(card['breakdown'])
    percent = value * 20
    return (f'<div class="tw-ring" role="img" aria-label="FinSignal Score: {value:.2f} из 5" '
            f'style="--score:{percent}%"><div><strong>{value:.2f}</strong><small>/ 5</small></div></div>')


def factor_bars(card):
    rows = []
    for key, label in FACTOR_NAMES.items():
        value = card['breakdown'][key]
        rows.append(f'<div class="tw-bar-row"><span>{escape(label)} <small>{WEIGHTS[key]:.0%}</small></span>'
                    f'<div class="tw-bar"><i style="width:{value*20}%"></i></div><b>{value:g}</b></div>')
    return '<div class="tw-bars">' + ''.join(rows) + '</div>'


def signal_art(card):
    """Abstract editorial graphic, not an image claimed to depict the source."""
    return '<div class="tw-orbit" aria-hidden="true"><div></div><i></i><b></b></div>'
