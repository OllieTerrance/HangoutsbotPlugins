"""
Integration with Google Calendar.

To generate the client secrets file::

    $ python -m plugins.gcal client_id client_secret path/to/secrets.json

Config keys (per-chat config goes under `conv_data.<conv_id>.gcal`):

    - `gcal.secrets` [global]: path to the generated secrets file
    - `gcal.id` [global, per-chat]: calendar ID (defaults to `primary`)
"""


from datetime import date, datetime, timedelta
from httplib2 import Http
import logging
import shlex

from dateutil.parser import parse
from googleapiclient.discovery import build
from oauth2client.client import OAuth2WebServerFlow
from oauth2client.file import Storage

import plugins


DATE = "%Y-%m-%d"
DATETIME = "%Y-%m-%dT%H:%M:%SZ"

logger = logging.getLogger(__name__)
config = None
api = None
resps = {}


def parse_date(d):
    start = parse(d, dayfirst=True, fuzzy=True, ignoretz=True) # can't handle tz
    return start.date() if start.hour == start.minute == 0 else start


def pretty_date(d):
    now = datetime.now()
    if isinstance(d, datetime):
        diff_secs = (d - now).seconds
        diff_days = (d.date() - now.date()).days
        if diff_secs < 0:
            return "now"
        elif diff_secs < 60 * 60:
            mins = diff_secs // 60
            return "in {} minute{}".format(mins, "" if mins == 1 else "s") # in 10 minutes
        elif diff_days == 0:
            return "today {}".format(d.strftime("%H:%M")) # today 11:30
        elif diff_days == 1:
            return "tomorrow {}".format(d.strftime("%H:%M")) # tomorrow 11:30
        elif 1 < diff_days < 7:
            return d.strftime("%A %H:%M") # Monday 11:30
        else:
            return d.strftime("%d/%m/%Y %H:%M") # 19/12/2016 11:30
    elif isinstance(d, date):
        now = now.date()
        diff = d - now
        if diff.days == 0:
            return "today"
        elif diff.days == 1:
            return "tomorrow"
        elif 1 < diff.days < 7:
            return d.strftime("%A") # Monday
        else:
            return d.strftime("%d/%m/%Y") # 19/12/2016


class Event(object):

    def __init__(self, api, cal, id, title, time, place=None, desc=None):
        self.api = api
        self.cal = cal
        self.id = id
        self.title = title
        self.time = time
        self.place = place
        self.desc = desc

    @classmethod
    def time_to_start(cls, time):
        if isinstance(time, datetime):
            return {"dateTime": time.strftime(DATETIME), "date": None}
        elif isinstance(time, date):
            return {"date": time.strftime(DATE), "dateTime": None}
        else:
            raise TypeError

    @classmethod
    def from_api(cls, api, cal, item):
        id = item["id"]
        title = item["summary"]
        if "dateTime" in item["start"]:
            time = datetime.strptime(item["start"]["dateTime"], DATETIME)
        elif "date" in item["start"]:
            time = datetime.strptime(item["start"]["date"], DATE).date()
        place = item.get("location")
        desc = item.get("description")
        return cls(api, cal, id, title, time, place, desc)

    @classmethod
    def create(cls, api, cal, title, time, place=None, desc=None):
        id = api.insert(calendarId=cal.id, body={"summary": title,
                                                 "start": cls.time_to_start(time),
                                                 "end": cls.time_to_start(time + timedelta(hours=1)),
                                                 "location": place,
                                                 "description": desc}).execute()["id"]
        return cls(api, cal, id, title, time, place, desc)

    def update(self, title=None, time=None, place=None, desc=None):
        data = {}
        if title:
            data["summary"] = title
        if time:
            data["start"] = self.time_to_start(time)
            data["end"] = self.time_to_start(time + timedelta(hours=1))
        if place is not None:
            data["location"] = place
        if desc is not None:
            data["description"] = desc
        self.api.patch(calendarId=self.cal.id, eventId=self.id, body=data).execute()
        if title:
            self.title = title
        if time:
            self.time = time
        if place is not None:
            self.place = place
        if desc is not None:
            self.desc = desc

    def delete(self):
        self.api.delete(calendarId=self.cal.id, eventId=self.id).execute()


class Calendar(object):

    def __init__(self, api, id):
        self.api = api
        self.id = id
        self.events = None

    def sync(self):
        resp = self.api.list(calendarId=self.id, timeMin=date.today().strftime(DATETIME),
                             singleEvents=True, orderBy="startTime").execute()
        self.events = [Event.from_api(api, self, item) for item in resp["items"]]

    def create(self, title, time, place=None, desc=None):
        return Event.create(self.api, self, title, time, place, desc)


class Responder(object):

    def __init__(self, cal):
        self.cal = cal

    def sync(self):
        self.cal.sync()

    def list(self):
        if self.cal.events is None:
            self.sync()
        if not self.cal.events:
            return "Nothing planned yet."
        msg = "Upcoming events:"
        for pos, event in enumerate(self.cal.events):
            msg += "\n{}. <b>{}</b> -- {}".format(pos + 1, event.title, pretty_date(event.time))
            if event.desc:
                msg += "\n<i>{}</i>".format(event.desc)
            if event.place:
                msg += "\n{}".format(event.place)
        return msg

    def show(self, pos):
        if self.cal.events is None:
            self.sync()
        try:
            event = self.cal.events[int(pos) - 1]
        except ValueError:
            return "Use the number given in the event list to remove events."
        except IndexError:
            return "Don't know about that event."
        else:
            msg = "<b>{}</b> -- {}".format(event.title, pretty_date(event.time))
            if event.desc:
                msg += "\n<i>{}</i>".format(event.desc)
            if event.place:
                msg += "\n{}".format(event.place)
            return msg

    def add(self, title, time_str, *args):
        try:
            time = parse_date(time_str)
        except ValueError:
            return "Couldn't parse the date.  Try writing it in <i>dd/mm/yyyy hh:mm</i> format."
        place = None
        desc = None
        if len(args) >= 2 and args[0] == "at":
            place = args[1]
            args = args[2:]
        if len(args) >= 1:
            desc = args[0]
        event = self.cal.create(title, time, place, desc)
        return "Added <b>{}</b> to the calendar.".format(event.title)

    def edit(self, pos, *args):
        if self.cal.events is None:
            self.sync()
        try:
            event = self.cal.events[int(pos) - 1]
        except ValueError:
            return "Use the number given in the event list to remove events."
        except IndexError:
            return "Don't know about that event."
        else:
            data = {}
            for field, value in zip(args[0::2], args[1::2]):
                if field == "time":
                    try:
                        value = parse_date(value)
                    except ValueError:
                        return "Couldn't parse the date.  Try writing it in <i>dd/mm/yyyy hh:mm</i> format."
                elif field not in ("title", "place", "desc"):
                    return "You can edit the <i>title</i>, <i>time</i>, <i>place</i> or <i>desc</i> of an event."
                data[field] = value
            event.update(**data)
            return "Updated <b>{}</b> on the calendar.".format(event.title)

    def remove(self, pos):
        if self.cal.events is None:
            self.sync()
        try:
            event = self.cal.events[int(pos) - 1]
        except ValueError:
            return "Use the number given in the event list to remove events."
        except IndexError:
            return "Don't know about that event."
        else:
            event.delete()
            return "Removed <b>{}</b> from the calendar.".format(event.title)


def _initialise(bot):
    global config, api
    config = bot.get_config_option("gcal")
    if not config or "secrets" not in config:
        logger.error("gcal: missing path to secrets file")
        return
    store = Storage(config["secrets"])
    http = store.get().authorize(Http())
    api = build("calendar", "v3", http=http).events()
    plugins.register_user_command(["calendar"])


def calendar(bot, event, *args):
    ("""Displays and manages upcoming events.<br>"""
     """- /bot calendar list<br>"""
     """- /bot calendar show <i>pos</i><br>"""
     """- /bot calendar add <i>\"what\"</i> <i>\"when\"</i> [at <i>\"where\"</i>] [<i>\"description\"</i>]<br>"""
     """- /bot calendar edit <i>pos</i> <i>field</i> <i>\"update\"</i> [...]<br>"""
     """- /bot calendar remove <i>pos</i>""")
    args = shlex.split(event.text)[2:] # better handling of quotes
    cal_id = None
    try:
        ho_config = bot.memory.get_by_path(["conv_data", event.conv.id_, "gcal"])
    except KeyError:
        ho_config = {}
        if not bot.memory.exists(["conv_data", event.conv.id_]):
            bot.memory.set_by_path(["conv_data", event.conv.id_], {})
        bot.memory.set_by_path(["conv_data", event.conv.id_, "gcal"], ho_config)
    cal_id = ho_config.get("id", config.get("id", "primary"))
    try:
        resp = resps[cal_id]
    except KeyError:
        resp = Responder(Calendar(api, cal_id))
    msg = None
    botalias = bot.memory.get("bot.command_aliases")[0]
    if not args:
        args = ["list"]
    if args[0] == "list":
        msg = resp.list()
    elif args[0] == "show":
        try:
            msg = resp.show(*args[1:])
        except TypeError:
            msg = "Usage: /bot calendar show <i>pos</i>"
    elif args[0] == "add":
        try:
            msg = resp.add(*args[1:])
        except TypeError:
            msg = "Usage: /bot calendar add <i>\"what\"</i> <i>\"when\"</i> [at <i>\"where\"</i>] [<i>\"description\"</i>]"
    elif args[0] == "edit":
        try:
            msg = resp.edit(*args[1:])
        except TypeError:
            msg = "Usage: /bot calendar edit <i>pos</i> <i>field</i> <i>\"update\"</i> [...]"
    elif args[0] == "remove":
        try:
            msg = resp.remove(*args[1:])
        except TypeError:
            msg = "Usage: /bot calendar remove <i>pos</i>"
    else:
        msg = "Unknown subcommand, try /bot help calendar."
    if msg:
        yield from bot.coro_send_message(event.conv_id, msg.replace("/bot", botalias))

calendar.__doc__ = calendar.__doc__.strip().replace("\n    ", "\n")


if __name__ == "__main__":

    from argparse import ArgumentParser

    from oauth2client import tools

    parser = ArgumentParser(parents=[tools.argparser])
    parser.add_argument("client_id", help="public key for Google APIs")
    parser.add_argument("client_secret", help="secret key for Google APIs")
    parser.add_argument("path", help="output file for the generated secrets file")
    args = parser.parse_args()

    flow = OAuth2WebServerFlow(client_id=args.client_id, client_secret=args.client_secret,
                               scope="https://www.googleapis.com/auth/calendar")
    tools.run_flow(flow, Storage(args.path), args)
