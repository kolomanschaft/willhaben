#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
The MIT License (MIT)

Copyright (c) 2012 Martin Hammerschmied

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

from profile import get_profile
from adstore import AdStore
from adassessor import AdAssessor, AdCriterion
from notificationserver import NotificationServer
from observer import Observer
import os

class CommandError(Exception):pass


class Command(object):
    """
    Base class for all commands.
    """

    def __init__(self, server, json_decoded):
        self._server = server
        self._json_decoded = json_decoded
    
    def execute(self):
        raise CommandError("Execute must be implemented in a subclass.")
    
    @classmethod
    def from_command_info(cls, server, cmd_info):
        if ("command" not in cmd_info):
            raise CommandError("The given data is not a valid command.")

        for cmd in Command.__subclasses__():
            if cmd.name == cmd_info["command"]:
                return cmd(server, cmd_info)
        
        raise CommandError("Unknown command: {}".format(cmd_info["command"]))


class SmtpSettingsCommand(Command):
    """
    Command to change the SMTP settings for sending email notifications.
    """
    name = "smtp_config"
    
    def execute(self):
        self.validate_smtp_config(self._json_decoded)
        if "user" not in self._json_decoded:
            self._json_decoded["user"] = None
        if "pass" not in self._json_decoded:
            self._json_decoded["pass"] = None
        self._server.config["smtp"] = self._json_decoded
    
    def validate_smtp_config(self, config):
        if ("host" not in config):
            raise CommandError("'host' is missing in the smtp configuration.")
        if ("port" not in config):
            raise CommandError("'port' is missing in the smtp configuration.")


class NewObserverCommand(Command):
    """
    Setup a new observer. If an older observer is running with the same name, 
    it will be replaced by the new observer.
    """
    name = "new_observer"

    def execute(self):
        self._server._logger.append("Setting up observer " + self._json_decoded["name"])
        profile = get_profile(self._json_decoded["profile"])
        store = self._setup_store()
        
        assessor = AdAssessor()
        for json in self._json_decoded["criteria"]:
            assessor.add_criterion(AdCriterion.from_json(json))
     
        # Notification server setup
        notificationServer = NotificationServer()
        for json in self._json_decoded["notifications"]:
            notification = self._setup_notification(json, profile)
            notificationServer.add_notification(notification)

        # Setup the actual observer
        observer = Observer(url = self._json_decoded["url"], profile = profile,
                            store = store, assessor = assessor,
                            notifications = notificationServer,
                            logger = self._server.logger,
                            update_interval = self._json_decoded["interval"],
                            name = self._json_decoded["name"])
        
        self._server.add_observer(observer)

    def _setup_store(self):
        save_file = None    # Ads that have already been processed are registered in this file
        if self._json_decoded["store"] == True:
            if not os.path.exists("./store/"): os.mkdir("store")
            save_file = "store/adstore.{}.db".format(self._json_decoded["name"])
        return AdStore(path = save_file)
    
    def _setup_notification(self, json, profile):
        if (json["type"] == "email"):
            if not self._server.config["smtp"]:
                raise CommandError("Cannot setup email notifications without smtp settings.")

            from notifications import EmailNotification
            formatting = profile.Notifications.Email
            smtp = self._server.config["smtp"]
            to = json["to"]
            if (type(to) == str):
                to = [to]   # make it a list
            email_notification = EmailNotification(smtp["host"], smtp["port"],
                                                   smtp["user"], smtp["pass"],
                                                   formatting.From, json["to"],
                                                   formatting.ContentType,
                                                   formatting.Subject,
                                                   formatting.Body.valueOf_)
            return email_notification
        
        
class RemoveObserverCommand(Command):
    """
    Command to remove an observer by its name.
    """
    name = "remove_observer"
    
    def execute(self):
        if "name" not in self._json_decoded:
            raise CommandError("The remove_observer command must specify a name.")
        self._server.remove_observer(self._json_decoded["name"])


class ListObserversCommand(Command):
    """
    Returns a list of all observers that are currently running.
    """
    name = "list_observers"
    
    def execute(self):
        return [observer.name for observer in self._server]


class GetObserverCommand(Command):
    """
    Returns a list of all observers that are currently running.
    """
    name = "get_observer"
    
    def execute(self):
        if "name" not in self._json_decoded:
            raise CommandError("The get_observer command must specify a name.")
        observer = self._server[self._json_decoded["name"]]
        if observer is None:
            raise CommandError("Observer {} not found.".format(self._json_decoded["name"]))
        return observer.serialize()


class ListCommandsCommand(Command):
    """
    Returns a list of all available commands.
    """
    name = "list_commands"
    
    def execute(self):
        return [cmd_class.command for cmd_class in Command.__subclasses__()]

