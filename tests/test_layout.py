"""cachereg.viz.layout: title wrapping."""

from PIL import Image, ImageDraw

from cachereg.render import one_line
from cachereg.viz.layout import _font, _wrap_balanced


def test_title_newline_is_a_preferred_break():
    d, font = ImageDraw.Draw(Image.new("RGB", (10, 10))), _font("display", 50)
    title = "DeepSeek serves more tokens on OpenRouter\nthan every US model combined."
    # Wide enough: the break is kept, whatever balancing would choose.
    assert _wrap_balanced(d, title, font, 1500) == [
        "DeepSeek serves more tokens on OpenRouter",
        "than every US model combined.",
    ]
    # Too narrow for the first line: the newline is ignored and the whole title is balanced.
    narrow = _wrap_balanced(d, title, font, 700)
    assert narrow == _wrap_balanced(d, one_line(title), font, 700)
    assert all(d.textlength(line, font=font) <= 700 for line in narrow)
    assert one_line(title) == "DeepSeek serves more tokens on OpenRouter than every US model combined."
