"""
General utility functions for FRHEED.
"""

import sys
import os
from typing import Union, Optional, Dict, Tuple
import logging
from pathlib import Path
import subprocess
import atexit

import numpy as np
from PyQt5.QtWidgets import QWidget, QApplication
from PyQt5.QtGui import QColor, QPen, QIcon

from frheed import settings
from frheed.constants import LOG_DIR


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """ Get a logger for FRHEED errors and messages. """
    # Use name if provided, otherwise `frheed`
    name = name or "frheed"
    
    # Generate log path
    filepath = os.path.join(LOG_DIR, f"{name}.log")
    
    # Create logger
    logger = logging.getLogger(name=name)
    
    # Make sure handlers haven't been added already
    # https://stackoverflow.com/a/59448231/10342097
    if logger.handlers:
        return logger
    
    # Set level to info
    logger.setLevel(logging.INFO)
    
    # Filter that logs only INFO and WARNING level messages
    class ConsoleFilter:
        def __init__(self, level: int):
            self.__level = level
            
        def filter(self, record) -> bool:
            return record.levelno in [logging.INFO, logging.WARNING]
    
    # Create file handler
    file_handler = logging.FileHandler(filepath, mode="a")
    file_format = "%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s] %(message)s"
    file_formatter = logging.Formatter(file_format)
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    
    # Create console handler
    console_handler = logging.StreamHandler()
    console_format = "%(message)s"
    console_formatter = logging.Formatter(console_format)
    console_handler.setFormatter(console_formatter)
    console_handler.addFilter(ConsoleFilter(logging.INFO))
    logger.addHandler(console_handler)
    
    # Notify that logfile was started
    logger.info(f"Started {name}.log")
    
    # Create function for closing all logger handlers
    def close_handlers() -> None:
        for handler in logger.handlers[:]:
            handler.close()
            logger.removeHandler(handler)
    
    # Close the logger when system exits
    atexit.register(close_handlers)
    
    return logger


def get_platform_bitsize() -> int:
    """
    Get the Windows platform bit size (32 or 64).

    Returns
    -------
    int
        Windows architecture bit size (either 32 or 64).

    """
    import struct
    
    bitsize = struct.calcsize("P") * 8
    
    return bitsize
    

def fit_screen(widget: QWidget, scale: float = 0.5) -> None:
    """ Fit a widget in the center of the main screen """
    from PyQt5.QtWidgets import QDesktopWidget
    
    # Get main screen geometry
    desktop = QDesktopWidget()
    screen = desktop.availableGeometry()
    tot_w, tot_h = screen.width(), screen.height()
    
    # Resize widget to 75% of available space
    w, h = int(tot_w * scale), int(tot_h * scale)
    widget.resize(w, h)
    
    # Move to center of screen
    dx, dy = int((tot_w - w) / 2), int((tot_h - h) / 2)
    widget.move(dx, dy)
    

def get_icon(name: str) -> QIcon:
    """ Get the icon with the given name from the icons directory as a QIcon. """
    from frheed.constants import ICONS_DIR
    return QIcon(os.path.join(ICONS_DIR, f"{name}.ico"))


def test_widget(
        widget_class: type, 
        block: bool = False,
        **kwargs
        ) -> Tuple[QWidget, QApplication]:
    """
    Create a widget from the provided class using the *args and **kwargs,
    and start a blocking application event loop if block = True.

    Parameters
    ----------
    widget_class : type
        Class of the widget to be created (NOT the widget itself).
    block : bool, optional
        Whether or not to start the blocking event loop automatically. 
        The default is False.
    *args
        Positional arguments to be passed to the widget_class.
    **kwargs
        Keyword arguments to be passed to the widget_class.

    Returns
    -------
    Tuple[QWidget, QApplication]
        A tuple containing the widget and QApplication instance.

    """
    
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import QLabel
    
    # Get QApplication instance
    app = QApplication.instance() or QApplication(["FRHEED"])
    app.setStyle(settings.APP_STYLE)
    
    # Create widget
    # NOTE: This MUST be done after creating the application instance
    # otherwise the Spyder kernel will crash without a traceback
    if widget_class is not None:
        widget = widget_class(**kwargs)
    else:
        widget = QLabel()
        widget.setText("Demo Widget")
        widget.setAlignment(Qt.AlignCenter)
    
    # Set window icon
    widget.setWindowIcon(get_icon("FRHEED"))
    
    # Set window title to the widget class name
    widget.setWindowTitle(widget.__class__.__name__)
    
    # This should be called by default, but just make sure
    app.lastWindowClosed.connect(app.quit)
    
    # Fit to screen
    fit_screen(widget)
    
    # Show the widget
    widget.show()
    
    # NOTE: _exec() starts a blocking loop; any code after will not run
    sys.exit(app.exec_()) if block else None
    
    return (widget, app)


def unit_string(
        value: Union[float, int], 
        unit: str, 
        sep: Optional[str] = None,
        precision: Optional[int] = 2
        ) -> str:
    """
    Format a unit string depending on the order of magnitude.
    For example: 3_000_000 µm -> 3 m if base_unit = "m".

    Parameters
    ----------
    value : Union[float, int]
        The value to format as a string with appropriate units.
    unit : str
        Unit, such as "m" for meters or "µm" for microns.
    sep : Optional[str], optional
        Separator between the value and the suffix. If the default of None
        is used, the separator will be a space (" ").
    precision : Optional[int], optional
        Floating point precision to format as. If the default of None is 
        used, the inferred format "{...:,g}" will be used.

    Returns
    -------
    str
        A formatted string displaying the value with appropriate units.

    """
    
    from math import floor, log10
    
    # Certain units should have particular specifiers
    no_space_units = ["%"]
    sep = sep or " "
    if unit and any(v in unit for v in no_space_units):
        sep = ""
    
    # If unit is specific one, return early
    if unit in ["dB", "Hz", "%"]:
        if precision:
            return f"{value:.{precision}f}{sep}{unit}"
        else:
            return f"{value:,g}{sep}{unit}"
    
    # If no unit is given, just format using :,g
    if not unit:
        unit_str = f"{value:,g}" if precision is None else f"{value:.{precision}f}"
        return unit_str
        
    # Get prefixes for magnitudes, e.g. 10^-9 -> "n" for "nano"
    prefixes = {
        -9:     "n",  # nano
        -6:     "µ",  # micro
        -3:     "m",  # milli
        -2:     "c",  # centi
        -1:     "d",  # deci
        0:      "",   # base units
        3:      "k",  # kilo
        6:      "M",  # mega
        9:      "G",  # giga
        }
    
    # For certain units, like seconds, only certain prefixes should be used
    if unit and unit[-1] == "s":
        prefixes = {mag: s for mag, s in prefixes.items() if mag % 3 == 0}
    
    # Get magnitudes from prefices
    magnitudes = {prefix: mag for mag, prefix in prefixes.items()}
    
    # Add entry for things like "u" instead of "µ"
    magnitudes["u"] = -6
    
    # Make sure value is > 0 so log is valid
    orig_value = value
    if value < 0:
        value = abs(value)
        sign = "-"
    else:
        sign = ""
    
    # Make sure unit is only a single character in case something like µm is given
    # and the first character is in magnitudes
    unit_type = unit[-1] if unit[0] in magnitudes else unit
    
    # Scale value if unit already has a magnitude, e.g. µs
    if len(unit) > 1:
        value *= (10 ** magnitudes.get(unit[0], 0))

    # Get order of magnitude
    if value != 0:
        magnitude = floor(log10(value))
    else:
        magnitude = 0
    
    # If magnitude is not in prefixes, find the closest prefix
    if magnitude not in prefixes:
        magnitude = sorted(prefixes.keys(), key=lambda p: abs(magnitude - p))[0]
        
    # Scale value by determined magnitude
    scaled_value = value / (10 ** magnitude)
    
    # Get unit prefix
    prefix = prefixes[magnitude]
    
    # Generate unit string
    if precision is None:
        unit_str = f"{sign}{scaled_value:,g}{sep}{prefix}{unit_type}"
    else:
        unit_str = f"{sign}{scaled_value:.{precision}f}{sep}{prefix}{unit_type}"
    
    return unit_str


def save_settings(
        settings: Dict[str, Dict[str, Union[bool, str, float, int]]], 
        name: str
        ) -> None:
    """
    Save a dictionary of settings to a .json file.

    Parameters
    ----------
    settings : Dict[str, Dict[str, Union[bool, str, float, int]]]
        A dictionary of the settings.
    name : str
        The name of the settings group to be saved.

    """
    import json
    from frheed.constants import CONFIG_DIR
    
    # TODO: Switch to using TOML config

    # Create dictionary with each setting represented by as dictionary
    # containing the value and type of that value so it can be converted back
    config = {}
    for group_name, setting_dict in settings.items():
        config[group_name] = {}
        for setting, value in setting_dict.items():
            config[group_name][setting] = {
                "value": value, 
                "type": type(value).__name__
                }
    
    # Get filepath
    path = os.path.join(CONFIG_DIR, f"{name}_settings.json")
    
    # Save the configuration file
    with open(path, "w") as f:
        json.dump(config, f, indent="\t")


def load_settings(name: str) -> Dict[str, Dict[str, Union[bool, str, float, int]]]:
    """
    Load a .json file into a dictionary of settings with proper types.

    Parameters
    ----------
    name : str
        The name of the settings group to be loaded.

    Returns
    -------
    dict
        Dictionary containing the settings with values converted 
    to their proper types.

    """
    import json
    from ast import literal_eval
    from frheed.constants import CONFIG_DIR
    
    # TODO: Switch to using TOML config files

    # Get filepath
    path = os.path.join(CONFIG_DIR, f"{name}_settings.json")
    
    # This will raise an OSError if the file doesn't exist or is inaccessible
    with open(path, "r") as f:
        json_dict = json.load(f)

    # Convert to proper types
    config = {}
    for group_name, setting_dict in json_dict.items():
        
        config[group_name] = {}
        
        for setting, info in setting_dict.items():
            string_value = info["value"]
            type_ = info["type"]

            # json will natively convert some objects
            if not isinstance(string_value, str):
                config[group_name][setting] = string_value
                continue

            # Convert booleans
            if type_ == "bool":
                value = literal_eval(string_value)
                
            # Keep strings as strings
            elif type_ in ["string", "str"]:
                value = string_value
                
            # Convert integers and floats
            elif type_ in ["float", "int"]:
                value = literal_eval(string_value)
                
            # Try to convert if some other type is specified
            else:
                try:
                    value = literal_eval(string_value)
                except ValueError:
                    value = string_value
                    
            # Store updated type
            config[group_name][setting] = value
        
    return config


def sample_array(
            w: int = 2048, 
            h: int = 1536, 
            channels: int = 3, 
            dtype: str = "uint8"
            ) -> np.ndarray:
    """
    Generate a sample numpy array with the given dimensions and dtype.

    Parameters
    ----------
    w : int, optional
        Width of the array. The default is 2048.
    h : int, optional
        Height of the array. The default is 1536.
    channels : int, optional
        Number of channels in the array. The default is 3.
    dtype : str, optional
        Data type of the array. The default is "uint8".

    Returns
    -------
    numpy.ndarray
        The resulting array with shape (h, w, channels) of type "dtype".

    """
    
    # Get the image shape
    shape = (h, w, channels) if channels > 1 else (h, w)
    
    # Create the array
    arr = (np.random.rand(*shape) * 255).astype(dtype)
    
    return arr

def get_qcolor(color: Union[str, tuple, QColor]) -> QColor:
    """ Create a QColor. See https://doc.qt.io/qt-5/qcolor.html """
    
    if isinstance(color, str):
        return QColor(color)
    
    elif isinstance(color, tuple):
        return QColor(*color)
    
    elif isinstance(color, QColor):
        return color
    
    else:
        raise TypeError(f"Unsupported color type {type(color)}")


def get_qpen(color: Union[str, tuple, QColor], cosmetic: bool = True) -> QColor:
    """ Create a QPen with the specified color """
    pen = QPen(get_qcolor(color))
    pen.setCosmetic(cosmetic)
    return pen


def snip_lists(*lists) -> list:
    min_len = min(map(len, lists))
    return [L[:min_len] for L in lists]
    

def get_locals(frame) -> dict:
    return dict(frame.f_back.f_locals.items())


def install_whl(filepath: str) -> int:
    """ Install a module using pip, either from a PyPi library or local file. """
    # Make sure .whl filepath and python.exe filepath are single-escaped
    python_path = sys.executable.replace("\\", "/")
    filepath = filepath.replace("\\", "/")
    
    # Use subprocess to execute the commands
    args = [python_path, "-m", "pip", "install", filepath]
    exit_code = subprocess.check_call(args)
    return exit_code


def gen_reqs() -> str:
    """ Create the requirements.txt file for FRHEED. """
    logger = get_logger("utils")
    python = sys.executable.replace("\\", "/")
    subprocess.check_call([python, "-m", "pip", "freeze", ">", "requirements.txt"])
    requirements = Path("requirements.txt").read_text()
    logger.info(f"Generated requirements:\n{requirements}")


if __name__ == "__main__":
    pass