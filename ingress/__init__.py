from datetime import datetime
import os
import re
import time

import plugins


def _initialise(bot):
    plugins.register_user_command(["cp", "glyph", "level"])


# Checkpoints and septicycles

checkpoint = 60 * 60 * 5
septicycle = checkpoint * 35

def calc(period, after=True):
    offset = 1 if after else 0
    ts = ((time.time() // period) + offset) * period
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")

def cp(bot, event, *args):
    """Displays the current checkpoint and septicycle."""
    parts = [("Septicycle start", calc(septicycle, False)),
             ("Septicycle end", calc(septicycle)),
             ("Previous checkpoint", calc(checkpoint, False)),
             ("Next checkpoint", calc(checkpoint))]
    msg = "\n".join("{0}: <b>{1}</b>".format(*args) for args in parts)
    yield from bot.coro_send_message(event.conv, msg)


# Glyph images
# (images from https://github.com/sauloaalmeida/ingress-glyphs)

images = os.path.join(os.path.dirname(os.path.realpath(__file__)), "glyphs")

def glyph(bot, event, *args):
    """Displays a glyph, e.g. <b>glyph resist</b>."""
    if not args:
        yield from bot.coro_send_message(event.conv, "Name a glyph and I can show it to you.")
        return
    name = "-".join(args).lower()
    for filename in os.listdir(images):
        if name in filename.rsplit(".", 1)[0].split("_"):
            image = yield from bot._client.upload_image(open(os.path.join(images, filename), "rb"), filename=filename)
            yield from bot.coro_send_message(event.conv, "", image_id=image)
            break
    else:
        yield from bot.coro_send_message(event.conv, "I don't recognise a glyph of that name.")


# Level-up requirements

levels = [None,
          "You already meet the requirements!",
          "2,500 AP",
          "20,000 AP",
          "70,000 AP",
          "150,000 AP",
          "300,000 AP",
          "600,000 AP",
          "1.2M AP",
          "2.4M AP + 1 gold + 4 silver",
          "4M AP + 2 gold + 5 silver",
          "6M AP + 4 gold + 6 silver",
          "8.4M AP + 6 gold + 7 silver",
          "12M AP + 1 platinum + 7 gold",
          "17M AP + 2 platinum + 7 gold",
          "24M AP + 3 platinum + 7 gold",
          "40M AP + 2 onyx + 4 platinum + 7 gold",
          "This information is classified."]

def level(bot, event, *args):
    """Displays level-up requirements, e.g. <b>level 16</b>."""
    if not args:
        parts = []
        for lv in range(2, 17):
            parts.append("<b>L{0}:</b> {1}".format(lv, levels[lv]))
        yield from bot.coro_send_message(event.conv, "\n".join(parts))
        return
    try:
        lv = int(args[0])
        if lv < 1 or lv > 17:
            raise ValueError
    except ValueError:
        yield from bot.coro_send_message(event.conv, "Level should be a number between 2 and 16.")
        return
    yield from bot.coro_send_message(event.conv, "<b>L{0}:</b> {1}".format(lv, levels[lv]))
