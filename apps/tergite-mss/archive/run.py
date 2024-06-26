# This code is part of Tergite
#
# (C) Copyright Miroslav Dobsicek 2019
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.


import configparser
from os import path

from mss.factory import create_app

config = configparser.ConfigParser()
config.read(path.abspath(path.join("config.ini")))

app = create_app()
app.config["DB_URI"] = config["DATABASE"]["DB_URI"]

if __name__ == "__main__":
    app.run()
