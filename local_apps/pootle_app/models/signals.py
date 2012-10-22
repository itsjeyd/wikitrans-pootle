#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2009 Zuza Software Foundation
#
# This file is part of translate.
#
# translate is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# translate is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with translate; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

from django.dispatch import Signal

post_vc_update = Signal(
    providing_args=["oldstats", "remotestats", "newstats"])
post_vc_commit = Signal(providing_args=["store", "stats", "user", "success"])
post_template_update = Signal(providing_args=["oldstats", "newstats"])
post_file_upload = Signal(
    providing_args=["user", "oldstats", "newstats", "archive"])
