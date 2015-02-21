# encoding: utf-8

# Nagstamon - Nagios status monitor for your desktop
# Copyright (C) 2008-2015 Henri Wahl <h.wahl@ifw-dresden.de> et al.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA

"""Module QUI"""

# for python2 and upcomping python3 compatiblity
from __future__ import print_function, absolute_import, unicode_literals

from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtSvg import *

import os
from operator import methodcaller
from collections import OrderedDict

from Nagstamon.Config import (conf, RESOURCES, APPINFO)

from Nagstamon.Servers import servers

from Nagstamon.Objects import GenericService

# fixed icons for hosts/services attributes
ICONS = dict()

# fixed shortened and lowered color names for cells
COLORS = {'WARNING':     'color_warning_',
          'CRITICAL':    'color_critical_',
          'DOWN':        'color_down_',
          'UNKNOWN':     'color_unknown_',
          'UNREACHABLE': 'color_unreachable_'}

class HBoxLayout(QHBoxLayout):
    """
        Apparently necessary to get a HBox which is able to hide its children
    """
    def __init__(self, spacing=None):
        QHBoxLayout.__init__(self)
        if not spacing == None:
            self.setSpacing(0)                      # no spaces necessary between items
        self.setContentsMargins(0, 0, 0, 0)     # no margin


    def hideItems(self):
        """
            cruise through all child widgets and hide them
            self,count()-1 is needed because the last item is None
        """
        for item in range(self.count()-1):
            self.itemAt(item).widget().hide()


    def showItems(self):
        """
            cruise through all child widgets and show them
            self,count()-1 is needed because the last item is None
        """
        for item in range(self.count()-1):
            self.itemAt(item).widget().show()


class SystemTrayIcon(QSystemTrayIcon):
    """
        Icon in system tray, works at least in Windows and OSX
        Qt5 shows an empty icon in GNOME3
    """
    def __init__(self, icon):
        QSystemTrayIcon.__init__(self, icon)
        self.menu = QMenu()
        exitaction = QAction("Exit", self)
        exitaction.triggered.connect(QCoreApplication.instance().quit)
        self.menu.addAction(exitaction)
        self.setContextMenu(self.menu)


class StatusWindow(QWidget):
    def __init__(self):
        """
            Status window combined from status bar and popup window
        """
        QWidget.__init__(self)
        #self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        self.setWindowFlags(Qt.WindowStaysOnTopHint)
        self.setWindowTitle(APPINFO.Name)
        self.setWindowIcon(QIcon('%s%snagstamon.svg' % (RESOURCES, os.sep)))

        self.vbox = QVBoxLayout(spacing=0)          # global VBox
        self.vbox.setContentsMargins(0, 0, 0, 0)    # no margin

        #self.bar_hbox = HBoxLayout(spacing=0)       # statusbar HBox
        self.top_hbox = HBoxLayout(spacing=10)      # top VBox containing buttons

        self.servers_vbox = QVBoxLayout()            # HBox full of servers
        self.servers_vbox.setContentsMargins(0, 0, 0, 0)

        self.servers_scrollarea = QScrollArea()     # scrollable area for server vboxes
        self.servers_scrollarea_widget = QWidget()  # necessary widget to contain vbox for servers

        self.createServerVBoxes()

        self.servers_scrollarea_widget.setLayout(self.servers_vbox)
        self.servers_scrollarea.setWidget(self.servers_scrollarea_widget)
        self.servers_scrollarea.setWidgetResizable(True)

        self.vbox.addLayout(self.bar_hbox)
        self.vbox.addLayout(self.top_hbox)
        self.vbox.addWidget(self.servers_scrollarea)

        # define label first to get its size for svg logo dimensions
        self.bar_label = QLabel(' 1 2 3 ')
        self.bar_label.setStyleSheet('background-color: green;')
        self.bar_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        # derive logo dimensions from status label
        self.bar_logo = QSvgWidget("%s%snagstamon_logo_bar.svg" % (RESOURCES, os.sep))
        self.bar_logo.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
        self.bar_logo.setMinimumSize(self.bar_label.fontMetrics().height(), self.bar_label.fontMetrics().height())

        self.bar_hbox.addWidget(self.bar_logo)
        self.bar_hbox.addWidget(self.bar_label)
        self.bar_hbox.addStretch()

        # top button box
        self.logo = QSvgWidget("%s%snagstamon_label.svg" % (RESOURCES, os.sep))
        self.logo.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)

        self.label_version = QLabel(APPINFO.Version)
        self.combobox_servers = QComboBox()
        self.button_filters = QPushButton("Filters")
        self.button_recheck_all = QPushButton("Recheck all")
        self.button_refresh = QPushButton("Refresh")
        self.button_settings = QPushButton("Settings")
        self.button_hamburger_menu = QPushButton()
        self.button_hamburger_menu.setIcon(QIcon("%s%smenu.svg" % (RESOURCES, os.sep)))
        self.button_close = QPushButton()
        self.button_close.setIcon(QIcon("%s%sclose.svg" % (RESOURCES, os.sep)))
        self.button_close.clicked.connect(self.close)

        self.top_hbox.addWidget(self.logo)
        self.top_hbox.addWidget(self.label_version)
        self.top_hbox.addStretch()
        self.top_hbox.addWidget(self.combobox_servers)
        self.top_hbox.addWidget(self.button_filters)
        self.top_hbox.addWidget(self.button_recheck_all)
        self.top_hbox.addWidget(self.button_refresh)
        self.top_hbox.addWidget(self.button_settings)
        self.top_hbox.addWidget(self.button_hamburger_menu)
        self.top_hbox.addWidget(self.button_close)

        self.setLayout(self.vbox)

        # icons in ICONS have to be sized as fontsize
        CreateIcons(self.bar_label.fontMetrics().height())


    def createServerVBoxes(self):
        """
            internally used to create enabled servers to be displayed
        """
        for server in servers.values():
            if server.enabled:
                self.servers_vbox.addLayout(ServerVBox(server))


class StatusBar(QLabel):
    """
        status bar is essentially a label
    """
    def __init__(self):
        QLabel.__init__(self)

        self.hbox = HBoxLayout(spacing=0)

        # define label first to get its size for svg logo dimensions
        self.label = QLabel(' 1 2 3 ')
        self.label.setStyleSheet('background-color: green;')
        self.label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        # derive logo dimensions from status label
        self.logo = QSvgWidget("%s%snagstamon_logo_bar.svg" % (RESOURCES, os.sep))
        self.logo.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
        self.logo.setMinimumSize(self.bar_label.fontMetrics().height(), self.bar_label.fontMetrics().height())

        self.hbox.addWidget(self.bar_logo)
        self.hbox.addWidget(self.bar_label)
        self.hbox.addStretch()


class ServerVBox(QVBoxLayout):
    """
        one VBox per server containing buttons and hosts/services listview
    """
    def __init__(self, server):
        QVBoxLayout.__init__(self)

        self.server = server

        hbox = QHBoxLayout(spacing=10)

        label = QLabel("<big><b>%s@%s</b></big>" % (server.username, server.name))
        button_server = QPushButton("Monitor")
        button_hosts = QPushButton("Hosts")
        button_services = QPushButton("Services")
        button_history = QPushButton("History")

        hbox.addWidget(label)
        hbox.addWidget(button_server)
        hbox.addWidget(button_hosts)
        hbox.addWidget(button_services)
        hbox.addWidget(button_history)
        hbox.addStretch()
        self.addLayout(hbox)

        self.headers = OrderedDict([('host', 'Host'), ('service', 'Service'),
                                    ('status', 'Status'), ('last_check', 'Last Check'),
                                    ('duration', 'Duration'), ('attempt', 'Attempt'),
                                    ('status_information', 'Status Information')])
        sort_column = 'status'
        order = 'descending'
        self.table = TableWidget(self.headers, 0, len(self.headers), sort_column, order, self.server)

        self.addWidget(self.table, 1)

        self.thread = QThread()
        self.worker = ServerThreadWorker(server=server)
        self.worker.moveToThread(self.thread)
        self.worker.new_status.connect(self.refresh)
        self.thread.started.connect(self.worker.refreshStatus)
        self.thread.start()


    def refresh(self):
        """
            refresh table cells with new data by thread
        """
        self.table.setData(list(self.server.GetItemsGenerator()))


class ServerThreadWorker(QObject):
    """
        attempt to run a server status update thread
    """

    new_status = pyqtSignal()

    def __init__(self, parent=None, server=None):
        QObject.__init__(self)
        self.server = server
        self.timer = QTimer(self)
        self.server.init_config()

    def refreshStatus(self):
        status =  self.server.GetStatus()
        self.new_status.emit()
        # avoid memory leak by singleshooting next refresh after this one is finished
        self.timer.singleShot(10000, self.refreshStatus)


class CellWidget(QWidget):
    def __init__(self, column=0, row=0, text='', color='black', background='white', icons=''):
        QWidget.__init__(self)

        self.column = column
        self.row = row
        self.text = text
        self.color = color
        self.background = background

        self.hbox = QHBoxLayout(self)
        self.setLayout(self.hbox)

        # text field
        self.label = QLabel(self.text)

        self.hbox.setContentsMargins(0, 0, 0, 0)
        self.hbox.addWidget(self.label, 1)
        self.hbox.setSpacing(0)

        self.label.setStyleSheet('padding: 5px;')

        # hosts and services might contain attribute icons
        if column in (0, 1) and icons is not False:
            for icon in icons:
                icon_label = QLabel()
                icon_label.setPixmap(icon.pixmap(self.label.fontMetrics().height(), self.label.fontMetrics().height()))
                icon_label.setStyleSheet('padding-right: 5px;')
                self.hbox.addWidget(icon_label)

        # paint cell appropriately
        self.colorize()


    def colorize(self):
        self.setStyleSheet('color: %s; background-color: %s;' % (self.color, self.background))


    def highlight(self):
        self.setStyleSheet('color: %s; background-color: %s;' % (self.color, 'darkgrey'))


    def enterEvent(self, event):
         self.parent().parent().highlightRow(self.row)


    def leaveEvent(self, event):
        self.parent().parent().colorizeRow(self.row)


class TableWidget(QTableWidget):
    def __init__(self, headers, columncount, rowcount, sort_column, order, server):
        QTableWidget.__init__(self, columncount, rowcount)

        self.SORT_ORDER = {'descending': True, 'ascending': False, 0: True, 1: False}

        self.headers = headers
        self.sort_column = sort_column
        self.order = order
        self.server = server

        # no vertical header needed
        self.verticalHeader().hide()

        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        # has to be necessarily false to keep sanity if calculating table height
        self.setShowGrid(False)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setAutoScroll(False)
        self.setSortingEnabled(True)

        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)

        self.setHorizontalHeaderLabels(self.headers.values())
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.horizontalHeader().setDefaultAlignment(Qt.AlignLeft)
        self.horizontalHeader().setStyleSheet('font-weight: bold;')
        self.horizontalHeader().setSortIndicatorShown(True)
        self.horizontalHeader().setSortIndicator(list(self.headers).index(self.sort_column), self.SORT_ORDER[self.order])
        self.horizontalHeader().sortIndicatorChanged.connect(self.sortColumn)


    def setData(self, data=None):
        """
            fill table cells with data from filtered Nagios items
        """
        # maximum size needs no more than amount of data
        self.setRowCount(self.server.nagitems_filtered_count)

        # temporary cache for cell widgets - first compute cells, store in self.data
        # then refresh cells from self.data
        # first list contains rows
        self.data = list()

        # to keep GTK Treeview sort behaviour first by services
        first_sort = sorted(data, key=methodcaller('compare_service'))
        for row, nagitem in enumerate(sorted(first_sort, key=methodcaller('compare_%s' % \
                                                (self.sort_column)), reverse=self.SORT_ORDER[self.order])):
            # lists in rows list are columns
            self.data.append(list())
            # create every cell per row
            for column, cell in enumerate(nagitem.get_columns(self.headers)):
                # check for icons to be used in cell widget
                if column in (0, 1):
                    icons = list()
                    # add host icons
                    if nagitem.is_host() and column == 0:
                        if nagitem.is_acknowledged():
                            icons.append(ICONS["acknowledged"])
                        if nagitem.is_flapping():
                            icons.append(ICONS["flapping"])
                        if nagitem.is_passive_only():
                            icons.append(ICONS["passive"])
                        if nagitem.is_in_scheduled_downtime():
                            icons.append(ICONS["downtime"])
                    # add host icons for service item - e.g. in case host is in downtime
                    elif not nagitem.is_host() and column == 0:
                        if self.server.hosts[nagitem.host].is_acknowledged():
                            icons.append(ICONS["acknowledged"])
                        if self.server.hosts[nagitem.host].is_flapping():
                            icons.append(ICONS["flapping"])
                        if self.server.hosts[nagitem.host].is_passive_only():
                            icons.append(ICONS["passive"])
                        if self.server.hosts[nagitem.host].is_in_scheduled_downtime():
                            icons.append(ICONS["downtime"])
                    # add service icons
                    elif not nagitem.is_host() and column == 1:
                        if nagitem.is_acknowledged():
                            icons.append(ICONS["acknowledged"])
                        if nagitem.is_flapping():
                            icons.append(ICONS["flapping"])
                        if nagitem.is_passive_only():
                            icons.append(ICONS["passive"])
                        if nagitem.is_in_scheduled_downtime():
                            icons.append(ICONS["downtime"])

                else:
                    icons = False
                widget = CellWidget(text=cell,
                                    color=conf.__dict__[COLORS[nagitem.status] + 'text'],
                                    background=conf.__dict__[COLORS[nagitem.status] + 'background'],
                                    row=row,
                                    column=column,
                                    icons=icons)
                self.data[row].append(widget)

        # fill cells with data
        for row in range(0, self.rowCount()):
            for column in range(0, len(self.headers)):
                self.setCellWidget(row, column, self.data[row][column])

        # seems to be important for not getting somehow squeezed cells
        self.resizeColumnsToContents()
        self.resizeRowsToContents()
        self.horizontalHeader().setStretchLastSection(True)

        # force table to its maximal height, calculated by .realHeight()
        self.setMinimumHeight(self.realHeight())
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Maximum)


    def sortColumn(self, column, order):
        """
            set data according to sort criteria
        """
        self.sort_column = self.headers.keys()[column]
        self.order = self.SORT_ORDER[order]
        self.setData(self.server.GetItemsGenerator())


    def realSize(self):
        """
            width, height
        """
        return self.realWidth(), self.realHeight()


    def realWidth(self):
        """
            calculate real table width as there is no method included
        """
        width = 0
        for c in range(0, self.columnCount()):
            width += self.cellWidget(0, c).width()
        del(c)

        return width


    def realHeight(self):
        """
            calculate real table height as there is no method included
        """
        # height summary starts with headers' height
        # apparently height works better/without scrollbar if some pixels are added
        height = self.horizontalHeader().height() + 2
        # it is necessary to ask every row directly because their heights differ :-(
        for row in range(0, self.rowCount()):
            height += (self.cellWidget(row, 0).height())
        del(row)

        return height


    def highlightRow(self, row):
        for column in range(0, self.columnCount()):
            if self.cellWidget(row, column) != None:
                self.cellWidget(row, column).highlight()


    def colorizeRow(self, row):
        for column in range(0, self.columnCount()):
            if self.cellWidget(row, column) != None:
                self.cellWidget(row, column).colorize()


def CreateIcons(fontsize):
    """
        fill global ICONS with pixmpas rendered from SVGs in fontsize dimensions
    """
    for attr in ('acknowledged', 'downtime', 'flapping', 'new', 'passive'):
        icon = QIcon('%s%snagstamon_%s.svg' % (RESOURCES, os.sep, attr))
        ICONS[attr] = icon

systrayicon = SystemTrayIcon(QIcon("%s%snagstamon.svg" % (RESOURCES, os.sep)))
statuswindow = StatusWindow()