import logging
import re
import shlex

from dateutil.parser import parse as date_parse
import requests

import plugins


log = logging.getLogger(__name__)


def _parse_args(bot, event):
    args = shlex.split(event.text)
    try:
        aliases = bot.memory.get_by_path(["bot.command_aliases"])
    except KeyError:
        aliases = ["/bot"]
    if args[0] in aliases:
        args.pop(0)
    return args


def _initialise(bot):
    plugins.register_user_command(["doodle", "doodle_email"])


def doodle(bot, event, *args):
    ("""Create a new Doodle poll: <b>doodle <i>"title" "option" ["option" ...] [+text] [+yesno] [+hidden]</i></b><br>"""
     """Use quotes to contain spaces.  Options are assumed to be dates, unless <b>+text</b> is used.<br>"""
     """Example: <i>doodle "My Event" 2016-01-01 2016-01-02 2016-01-03 +hidden</i><br>"""
     """You'll need to give Doodle an email address first -- use the <b>doodle_email</b> command to set one.""")
    args = _parse_args(bot, event)
    kwargs = {"ifNeedBe": "true", "hidden": "false", "options[]": []}
    for arg in args[1:]:
        if arg[0] == "+":
            flag = arg[1:]
            if flag == "text":
                kwargs["type"] = "TEXT"
            elif flag == "yesno":
                kwargs["ifNeedBe"] = "false"
            elif flag == "hidden":
                kwargs["hidden"] = "true"
            else:
                yield from bot.coro_send_message(event.conv_id, "<i>Didn't recognise flag <b>{0}</b>.</i>".format(flag))
                return
        elif "title" in kwargs:
            kwargs["options[]"].append(arg)
        else:
            kwargs["title"] = arg
    if "title" not in kwargs or not kwargs["options[]"]:
        yield from bot.coro_send_message(event.conv_id, "<i>Needs a title and at least one option.</i>")
        return
    if "type" not in kwargs:
        dates = []
        try:
            for opt in kwargs["options[]"]:
                dates.append(date_parse(opt))
        except ValueError:
            log.debug("Failed to parse a date, defaulting to text poll type")
            kwargs["type"] = "TEXT"
        else:
            fmt = "%Y%m%d%H%M" if any((d.hour > 0 or d.minute > 0) for d in dates) else "%Y%m%d"
            log.debug("Using date poll type{0}".format("" if fmt == "%Y%M%D" else " with times"))
            kwargs.update({"type": "DATE", "options[]": [d.strftime(fmt) for d in dates]})
    try:
        email = bot.memory.get_by_path(["user_data", event.user.id_.chat_id, "doodle_email"])
    except KeyError:
        yield from bot.coro_send_message(event.conv_id, "<i>No Doodle email set (see <b>help doodle_email</b>).</i>")
        return
    kwargs.update({"initiatorEmail": email, "initiatorAlias": event.user.full_name,
                   "optionsMode": kwargs["type"].lower()})
    log.info("Creating {0} poll \"{1}\"".format(kwargs["optionsMode"], kwargs["title"]))
    resp = requests.post("https://doodle.com/np/new-polls/", data=kwargs)
    if not resp.ok:
        yield from bot.coro_send_message(event.conv_id, "Got a {} response from Doodle...".format(resp.status_code))
        return
    json = resp.json()
    yield from bot.coro_send_message(event.conv_id, """Doodle created! <a href="https://doodle.com/poll/{0}">"""
                                                    "https://doodle.com/poll/{0}</a>".format(json["id"]))
    user_1to1 = yield from bot.get_1to1(event.user_id.chat_id)
    yield from bot.coro_send_message(user_1to1, "Here's the administration link for your Doodle poll: "
                                                """<a href="https://doodle.com/poll/{0}{1}/admin">"""
                                                "https://doodle.com/poll/{0}{1}/admin</a>"
                                                .format(json["id"], json["adminKey"]))


def doodle_email(bot, event, *args):
    ("""Set an email address to be used for Doodle poll administration: <b>doodle_email <i>email</i></b><br>"""
     """This address will receive email notifications when other people fill in the poll.""")
    if args:
        bot.memory.set_by_path(["user_data", event.user.id_.chat_id, "doodle_email"], args[0])
        bot.memory.save()
        yield from bot.coro_send_message(event.conv_id, "<i>Your Doodle email has been set.</i>")
    else:
        try:
            email = bot.memory.set_by_path(["user_data", event.user.id_.chat_id, "doodle_email"])
            yield from bot.coro_send_message(event.conv_id, "<i>Your Doodle email is set.  You can update it "
                                                            "with <b>doodle_email [new email]</b>.</i>")
        except KeyError:
            yield from bot.coro_send_message(event.conv_id, "<i>No Doodle email on record.  You can set one "
                                                            "with <b>doodle_email [new email]</b>.</i>")
