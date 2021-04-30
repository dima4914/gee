# -*- coding: utf-8 -*-
"""
/***************************************************************************
 GEEManager
                                 A QGIS plugin
 This plugin implements user-friendly interface (GUI) to make access to Goggle Earth Engine server easier
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                             -------------------
        begin                : 2020-12-31
        copyright            : (C) 2020 by Dima Okunev
        email                : dima@
        git sha              : $Format:%H$
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
 This script initializes the plugin, making it known to QGIS.
"""
import site
import pkg_resources
import os
# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load GEEManager class from file GEEManager.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    extra_libs_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'extlibs_windows'))

    # add to python path
    site.addsitedir(extra_libs_path)
    # pkg_resources doesn't listen to changes on sys.path.
    pkg_resources.working_set.add_entry(extra_libs_path)
    from .geeGUI import GEEManager
    return GEEManager(iface)