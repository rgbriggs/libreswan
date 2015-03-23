# Stuff to talk to virsh, for libreswan
#
# Copyright (C) 2015 Andrew Cagney <cagney@gnu.org>
# 
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; either version 2 of the License, or (at your
# option) any later version.  See <http://www.fsf.org/copyleft/gpl.txt>.
# 
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
# or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License
# for more details.

import os
import sys
import logging
import random

TIMEOUT = 10
SEARCH_WINDOW_SIZE = 100

# The following prompt is assumed.  It only displays status when it is
# non-zero:
PS1='[\\u@\\h \\W$(x=$? ; test $x -ne 0 && echo " $x")]\\$ '
#PS1='[\\u@\\h \\W $?]\\$ '

# Named groups for each part of the above
USERNAME_GROUP = "username"
HOSTNAME_GROUP = "hostname"
BASENAME_GROUP = "basename"
STATUS_GROUP = "status"
DOLLAR_GROUP = "dollar"

# Patterns for each part of the above prompt
USERNAME_PATTERN = "[-\.a-z0-9]+"
HOSTNAME_PATTERN = "[-a-z0-9]+"
BASENAME_PATTERN = "[-\.a-z0-9A-Z_~]+"
STATUS_PATTERN = "| [0-9]+"
DOLLAR_PATTERN = "[#\$]"

# Create a prompt regex that either matches directly or after the
# event.
class PromptPattern:

    # Generate a pattern that matches the prompt.  Only USERNAME and
    # HOSTNAME should be overridden.
    def __init__(self, username=None, hostname=None, basename=None, dollar=None):
        # Fix up dollar when username specified
        if not dollar and username:
            if username == "root":
                dollar = "#"
            else:
                dollar = "$"
        self.prompt = "\[(?P<" + USERNAME_GROUP + ">" + (username or USERNAME_PATTERN) + ")" + \
                      "@(?P<" + HOSTNAME_GROUP + ">"  + (hostname or HOSTNAME_PATTERN) + ")" + \
                      " (?P<" + BASENAME_GROUP + ">"  + (basename or BASENAME_PATTERN) + ")" + \
                      "(?P<" + STATUS_GROUP + ">" + (STATUS_PATTERN) + ")" + \
                      "\](?P<" + DOLLAR_GROUP + ">"  + (dollar or DOLLAR_PATTERN)  + ")" + \
                      " "
        logging.debug("prompt-pattern: %s", self.prompt)
        self.status = None

    # XXX: so '"%s%s" % (pattern, prompt)" works; better way?
    def __str__(self):
        return self.prompt

    def check_group(self, match, expected, field):
        if expected:
            found = match.group(field)
            logging.debug("prompt field: '%s' expected: '%s' found: '%s'", field, expected, found)
            if expected != found:
                # Throw TIMEOUT as that is what is expected and what
                # would have happened.
                pexpect.TIMEOUT("incorrect prompt, field '%s' should be '%s but was '%s'" \
                                % (self.field, self.expected, self.found))

    def check(self, match, hostname=None, username=None, basename=None, dollar=None):
        logging.debug("match %s", match)
        for group in match.groups():
            logging.debug("group: %s", group)
        self.check_group(match, hostname, HOSTNAME_GROUP)
        self.check_group(match, username, USERNAME_GROUP)
        self.check_group(match, basename, BASENAME_GROUP)
        self.check_group(match, dollar, DOLLAR_GROUP)
        status = match.group(STATUS_GROUP)
        if status:
            self.status = int(status)
        else:
            self.status = None
        logging.debug("prompt status: %s", self.status)

class Remote:

    def __init__(self, child, hostname, username):
        self.child = child
        self.basename = None
        self.prompt = PromptPattern(hostname=hostname, username=username)
        # get it into the expected mode
        self.run("export TERM=dumb; unset LS_COLORS; stty sane -echo -onlcr")
        # force a sync, use a random number
        number = str(random.randrange(1000000, 100000000))
        self.run("echo sync=" + number + "=sync", expect="sync=" + number + "=sync\\s*")
        # Fix the prompt
        self.run("PS1='" + PS1 + "'")

    def echo(self):
        # get it back into echo mode for interactive use
        self.run('export TERM=dumb; unset LS_COLORS; stty sane')

    def run(self, command, expect="", timeout=TIMEOUT):
        logging.debug("shell send '%s'", command)
        self.child.sendline(command)
        # This can throw a pexpect.TIMEOUT or pexpect.EOF exception
        match = "%s%s" % (expect, self.prompt)
        logging.debug("shell match '%s'", match)
        self.child.expect(match, timeout=timeout, \
                          searchwindowsize=SEARCH_WINDOW_SIZE)
        self.prompt.check(self.child.match, basename=self.basename)
        return self.prompt.status

    def chdir(self, directory):
        self.basename = os.path.basename(directory)
        return self.run("cd %s" % directory)