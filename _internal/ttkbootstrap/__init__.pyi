from __future__ import annotations

"""
PEP 561 stub augmentations for ttkbootstrap's public API.

These stubs add typing for ttkbootstrap's monkey‑patched ttk widgets so
they accept the named keyword argument `bootstyle` in both the widget
constructor and in `configure(...)` while retaining the base ttk types.

Target: Python 3.9+
"""

from typing import Any, Optional, Tuple, Union

from tkinter import (
    Menu as _tkMenu,
    Text as _tkText,
    Canvas as _tkCanvas,
    Tk as _tkTk,
    Frame as _tkFrame,
    Variable,
    StringVar,
    IntVar,
    BooleanVar,
    DoubleVar,
    PhotoImage,
)
from tkinter import ttk as _ttk

from ttkbootstrap.style import Bootstyle, Style
from ttkbootstrap.window import Toplevel, Window
from ttkbootstrap.widgets import (
    DateEntry,
    Floodgauge,
    FloodgaugeLegacy,
    LabeledScale,
    Meter,
)

# A bootstyle can be a single keyword (e.g. "primary") or a tuple
# of keywords (e.g. ("danger", "inverse"))
BootstyleArg = Union[str, Tuple[str, ...]]


class _BootstyleMixin:
    def __init__(self, *args: Any, bootstyle: Optional[BootstyleArg] = ..., **kwargs: Any) -> None: ...

    def configure(self, *args: Any, bootstyle: Optional[BootstyleArg] = ..., **kwargs: Any) -> Any: ...


# TTK widgets with bootstyle parameter
class Button(_ttk.Button):
    """TTK Button widget with ttkbootstrap theming support.

    A button widget that can display text and images and invoke a command when pressed.

    Args:
        master: Parent widget.
        class_: Widget class name for styling.
        command: Function or method to call when button is pressed.
        compound: How to display text and image together (text, image, top, bottom, left, right, center, none).
        cursor: Cursor to display when mouse is over the widget.
        default: Whether button is the default button (normal, active, disabled).
        image: Image to display on the button.
        name: Widget name.
        padding: Extra space around the button contents.
        state: Widget state (normal, active, disabled, readonly).
        style: Custom ttk style name.
        takefocus: Whether widget accepts focus during keyboard traversal.
        text: Text to display on the button.
        textvariable: Variable linked to the button text.
        underline: Index of character to underline in text.
        width: Width of the button in characters.
        bootstyle: ttkbootstrap style keywords for theming (e.g., 'primary', 'success.outline').
                   Can be a string or tuple of keywords. Use this instead of 'style' for
                   ttkbootstrap theming.
    """

    def __init__(
            self,
            master: Any = ...,
            *,
            class_: str = ...,
            command: Any = ...,
            compound: Any = ...,
            cursor: str = ...,
            default: Any = ...,
            image: Any = ...,
            name: str = ...,
            padding: Any = ...,
            state: str = ...,
            style: str = ...,
            takefocus: Any = ...,
            text: Any = ...,
            textvariable: Any = ...,
            underline: int = ...,
            width: Any = ...,
            bootstyle: Optional[BootstyleArg] = ...,
    ) -> None: ...

    def configure(self, cnf: Any = ..., *, bootstyle: Optional[BootstyleArg] = ..., **kwargs: Any) -> Any: ...

    config = configure


class Checkbutton(_ttk.Checkbutton):
    """TTK Checkbutton widget with ttkbootstrap theming support.

    A checkbutton widget that displays a checkbox with optional text and image.
    Can be toggled on/off and linked to a variable.

    Args:
        master: Parent widget.
        class_: Widget class name for styling.
        command: Function or method to call when checkbutton state changes.
        compound: How to display text and image together (text, image, top, bottom, left, right, center, none).
        cursor: Cursor to display when mouse is over the widget.
        image: Image to display on the checkbutton.
        name: Widget name.
        offvalue: Value to set variable to when checkbutton is off.
        onvalue: Value to set variable to when checkbutton is on.
        padding: Extra space around the checkbutton contents.
        state: Widget state (normal, active, disabled, readonly).
        style: Custom ttk style name.
        takefocus: Whether widget accepts focus during keyboard traversal.
        text: Text to display next to the checkbox.
        textvariable: Variable linked to the checkbutton text.
        underline: Index of character to underline in text.
        variable: Variable linked to the checkbutton state.
        width: Width of the checkbutton in characters.
        bootstyle: ttkbootstrap style keywords for theming (e.g., 'primary', 'success.toolbutton').
                   Can be a string or tuple of keywords. Use this instead of 'style' for
                   ttkbootstrap theming.
    """

    def __init__(
            self,
            master: Any = ...,
            *,
            class_: str = ...,
            command: Any = ...,
            compound: Any = ...,
            cursor: str = ...,
            image: Any = ...,
            name: str = ...,
            offvalue: Any = ...,
            onvalue: Any = ...,
            padding: Any = ...,
            state: str = ...,
            style: str = ...,
            takefocus: Any = ...,
            text: Any = ...,
            textvariable: Any = ...,
            underline: int = ...,
            variable: Any = ...,
            width: Any = ...,
            bootstyle: Optional[BootstyleArg] = ...,
    ) -> None: ...

    def configure(self, cnf: Any = ..., *, bootstyle: Optional[BootstyleArg] = ..., **kwargs: Any) -> Any: ...

    config = configure


class Combobox(_ttk.Combobox):
    """TTK Combobox widget with ttkbootstrap theming support.

    A combobox widget that combines a text entry with a dropdown list of values.
    User can either type a value or select from the list.

    Args:
        master: Parent widget.
        background: Background color of the entry field.
        class_: Widget class name for styling.
        cursor: Cursor to display when mouse is over the widget.
        exportselection: Whether to export selection to X selection.
        font: Font for the entry text.
        foreground: Foreground (text) color of the entry field.
        height: Number of rows to display in dropdown list.
        invalidcommand: Command to call when validation fails.
        justify: Text justification (left, center, or right).
        name: Widget name.
        postcommand: Command to call before dropdown is posted.
        show: Character to display instead of actual characters (for passwords).
        state: Widget state (normal, readonly, disabled).
        style: Custom ttk style name.
        takefocus: Whether widget accepts focus during keyboard traversal.
        textvariable: Variable linked to the entry text.
        validate: When to validate (none, focus, focusin, focusout, key, all).
        validatecommand: Command to call to validate input.
        values: List of values to display in dropdown.
        width: Width of the entry field in characters.
        xscrollcommand: Command to call when entry x-view changes.
        bootstyle: ttkbootstrap style keywords for theming (e.g., 'primary', 'danger').
                   Can be a string or tuple of keywords. Use this instead of 'style' for
                   ttkbootstrap theming.
    """

    def __init__(
            self,
            master: Any = ...,
            *,
            background: str = ...,
            class_: str = ...,
            cursor: str = ...,
            exportselection: bool = ...,
            font: Any = ...,
            foreground: str = ...,
            height: int = ...,
            invalidcommand: Any = ...,
            justify: Any = ...,
            name: str = ...,
            postcommand: Any = ...,
            show: Any = ...,
            state: str = ...,
            style: str = ...,
            takefocus: Any = ...,
            textvariable: Any = ...,
            validate: Any = ...,
            validatecommand: Any = ...,
            values: Any = ...,
            width: int = ...,
            xscrollcommand: Any = ...,
            bootstyle: Optional[BootstyleArg] = ...,
    ) -> None: ...

    def configure(self, cnf: Any = ..., *, bootstyle: Optional[BootstyleArg] = ..., **kwargs: Any) -> Any: ...

    config = configure


class Entry(_ttk.Entry):
    """TTK Entry widget with ttkbootstrap theming support.

    A single-line text entry widget that allows the user to enter text.
    Supports validation and can be linked to a variable.

    Args:
        master: Parent widget.
        widget: Internal widget parameter.
        background: Background color of the entry.
        class_: Widget class name for styling.
        cursor: Cursor to display when mouse is over the widget.
        exportselection: Whether to export selection to X selection.
        font: Font for the entry text.
        foreground: Foreground (text) color of the entry.
        invalidcommand: Command to call when validation fails.
        justify: Text justification (left, center, or right).
        name: Widget name.
        show: Character to display instead of actual characters (for passwords).
        state: Widget state (normal, readonly, disabled).
        style: Custom ttk style name.
        takefocus: Whether widget accepts focus during keyboard traversal.
        textvariable: Variable linked to the entry text.
        validate: When to validate (none, focus, focusin, focusout, key, all).
        validatecommand: Command to call to validate input.
        width: Width of the entry in characters.
        xscrollcommand: Command to call when entry x-view changes.
        bootstyle: ttkbootstrap style keywords for theming (e.g., 'info', 'warning').
                   Can be a string or tuple of keywords. Use this instead of 'style' for
                   ttkbootstrap theming.
    """

    def __init__(
            self,
            master: Any = ...,
            widget: Any = ...,
            *,
            background: str = ...,
            class_: str = ...,
            cursor: str = ...,
            exportselection: bool = ...,
            font: Any = ...,
            foreground: str = ...,
            invalidcommand: Any = ...,
            justify: Any = ...,
            name: str = ...,
            show: str = ...,
            state: str = ...,
            style: str = ...,
            takefocus: Any = ...,
            textvariable: Any = ...,
            validate: Any = ...,
            validatecommand: Any = ...,
            width: int = ...,
            xscrollcommand: Any = ...,
            bootstyle: Optional[BootstyleArg] = ...,
    ) -> None: ...

    def configure(self, cnf: Any = ..., *, bootstyle: Optional[BootstyleArg] = ..., **kwargs: Any) -> Any: ...

    config = configure


class Frame(_ttk.Frame):
    """TTK Frame widget with ttkbootstrap theming support.

    A container widget that groups other widgets. Frames provide structure
    and organization to the GUI layout.

    Args:
        master: Parent widget.
        border: Border width (alias for borderwidth).
        borderwidth: Width of the border around the frame.
        class_: Widget class name for styling.
        cursor: Cursor to display when mouse is over the widget.
        height: Height of the frame.
        name: Widget name.
        padding: Extra space inside the frame border.
        relief: 3D effect for the border (flat, raised, sunken, groove, ridge).
        style: Custom ttk style name.
        takefocus: Whether widget accepts focus during keyboard traversal.
        width: Width of the frame.
        bootstyle: ttkbootstrap style keywords for theming (e.g., 'primary', 'dark').
                   Can be a string or tuple of keywords. Use this instead of 'style' for
                   ttkbootstrap theming.
    """

    def __init__(
            self,
            master: Any = ...,
            *,
            border: Any = ...,
            borderwidth: Any = ...,
            class_: str = ...,
            cursor: str = ...,
            height: Any = ...,
            name: str = ...,
            padding: Any = ...,
            relief: Any = ...,
            style: str = ...,
            takefocus: Any = ...,
            width: Any = ...,
            bootstyle: Optional[BootstyleArg] = ...,
    ) -> None: ...

    def configure(self, cnf: Any = ..., *, bootstyle: Optional[BootstyleArg] = ..., **kwargs: Any) -> Any: ...

    config = configure


class Labelframe(_ttk.Labelframe):
    """TTK Labelframe widget with ttkbootstrap theming support.

    A frame widget with a label. Used to group related widgets together
    with a descriptive label.

    Args:
        master: Parent widget.
        border: Border width (alias for borderwidth).
        borderwidth: Width of the border around the frame.
        class_: Widget class name for styling.
        cursor: Cursor to display when mouse is over the widget.
        height: Height of the frame.
        labelanchor: Position of the label (nw, n, ne, en, e, es, se, s, sw, ws, w, wn).
        labelwidget: Custom widget to use as the label.
        name: Widget name.
        padding: Extra space inside the frame border.
        relief: 3D effect for the border (flat, raised, sunken, groove, ridge).
        style: Custom ttk style name.
        takefocus: Whether widget accepts focus during keyboard traversal.
        text: Text to display in the label.
        underline: Index of character to underline in label text.
        width: Width of the frame.
        bootstyle: ttkbootstrap style keywords for theming (e.g., 'info', 'secondary').
                   Can be a string or tuple of keywords. Use this instead of 'style' for
                   ttkbootstrap theming.
    """

    def __init__(
            self,
            master: Any = ...,
            *,
            border: Any = ...,
            borderwidth: Any = ...,
            class_: str = ...,
            cursor: str = ...,
            height: Any = ...,
            labelanchor: Any = ...,
            labelwidget: Any = ...,
            name: str = ...,
            padding: Any = ...,
            relief: Any = ...,
            style: str = ...,
            takefocus: Any = ...,
            text: Any = ...,
            underline: int = ...,
            width: Any = ...,
            bootstyle: Optional[BootstyleArg] = ...,
    ) -> None: ...

    def configure(self, cnf: Any = ..., *, bootstyle: Optional[BootstyleArg] = ..., **kwargs: Any) -> Any: ...

    config = configure


class Label(_ttk.Label):
    """TTK Label widget with ttkbootstrap theming support.

    A widget that displays text and/or an image. Labels are typically used
    to provide information or describe other widgets.

    Args:
        master: Parent widget.
        anchor: Position of text/image (nw, n, ne, w, center, e, sw, s, se).
        background: Background color of the label.
        border: Border width (alias for borderwidth).
        borderwidth: Width of the border around the label.
        class_: Widget class name for styling.
        compound: How to display text and image together (text, image, top, bottom, left, right, center, none).
        cursor: Cursor to display when mouse is over the widget.
        font: Font for the label text.
        foreground: Foreground (text) color of the label.
        image: Image to display on the label.
        justify: Multi-line text justification (left, center, or right).
        name: Widget name.
        padding: Extra space around the label contents.
        relief: 3D effect for the border (flat, raised, sunken, groove, ridge).
        state: Widget state (normal or disabled).
        style: Custom ttk style name.
        takefocus: Whether widget accepts focus during keyboard traversal.
        text: Text to display on the label.
        textvariable: Variable linked to the label text.
        underline: Index of character to underline in text.
        width: Width of the label in characters.
        wraplength: Maximum line length before text wraps.
        bootstyle: ttkbootstrap style keywords for theming (e.g., 'inverse', 'success').
                   Can be a string or tuple of keywords. Use this instead of 'style' for
                   ttkbootstrap theming.
    """

    def __init__(
            self,
            master: Any = ...,
            *,
            anchor: Any = ...,
            background: str = ...,
            border: Any = ...,
            borderwidth: Any = ...,
            class_: str = ...,
            compound: Any = ...,
            cursor: str = ...,
            font: Any = ...,
            foreground: str = ...,
            image: Any = ...,
            justify: Any = ...,
            name: str = ...,
            padding: Any = ...,
            relief: Any = ...,
            state: str = ...,
            style: str = ...,
            takefocus: Any = ...,
            text: Any = ...,
            textvariable: Any = ...,
            underline: int = ...,
            width: Any = ...,
            wraplength: Any = ...,
            bootstyle: Optional[BootstyleArg] = ...,
    ) -> None: ...

    def configure(self, cnf: Any = ..., *, bootstyle: Optional[BootstyleArg] = ..., **kwargs: Any) -> Any: ...

    config = configure


class Menubutton(_ttk.Menubutton):
    """TTK Menubutton widget with ttkbootstrap theming support.

    A button that displays a menu when clicked. Used for dropdown menus
    and menu navigation.

    Args:
        master: Parent widget.
        class_: Widget class name for styling.
        compound: How to display text and image together (text, image, top, bottom, left, right, center, none).
        cursor: Cursor to display when mouse is over the widget.
        direction: Where to display the menu relative to button (above, below, left, right, flush).
        image: Image to display on the menubutton.
        menu: Menu widget to display when button is clicked.
        name: Widget name.
        padding: Extra space around the menubutton contents.
        state: Widget state (normal, active, disabled).
        style: Custom ttk style name.
        takefocus: Whether widget accepts focus during keyboard traversal.
        text: Text to display on the menubutton.
        textvariable: Variable linked to the menubutton text.
        underline: Index of character to underline in text.
        width: Width of the menubutton in characters.
        bootstyle: ttkbootstrap style keywords for theming (e.g., 'primary.link', 'outline').
                   Can be a string or tuple of keywords. Use this instead of 'style' for
                   ttkbootstrap theming.
    """

    def __init__(
            self,
            master: Any = ...,
            *,
            class_: str = ...,
            compound: Any = ...,
            cursor: str = ...,
            direction: Any = ...,
            image: Any = ...,
            menu: Any = ...,
            name: str = ...,
            padding: Any = ...,
            state: str = ...,
            style: str = ...,
            takefocus: Any = ...,
            text: Any = ...,
            textvariable: Any = ...,
            underline: int = ...,
            width: Any = ...,
            bootstyle: Optional[BootstyleArg] = ...,
    ) -> None: ...

    def configure(self, cnf: Any = ..., *, bootstyle: Optional[BootstyleArg] = ..., **kwargs: Any) -> Any: ...

    config = configure


class Notebook(_ttk.Notebook):
    """TTK Notebook widget with ttkbootstrap theming support.

    A tabbed container widget that displays one of several pages at a time.
    Each page is associated with a tab.

    Args:
        master: Parent widget.
        class_: Widget class name for styling.
        cursor: Cursor to display when mouse is over the widget.
        height: Height of the notebook.
        name: Widget name.
        padding: Extra space inside the notebook.
        style: Custom ttk style name.
        takefocus: Whether widget accepts focus during keyboard traversal.
        width: Width of the notebook.
        bootstyle: ttkbootstrap style keywords for theming (e.g., 'primary', 'secondary').
                   Can be a string or tuple of keywords. Use this instead of 'style' for
                   ttkbootstrap theming.
    """

    def __init__(
            self,
            master: Any = ...,
            *,
            class_: str = ...,
            cursor: str = ...,
            height: int = ...,
            name: str = ...,
            padding: Any = ...,
            style: str = ...,
            takefocus: Any = ...,
            width: int = ...,
            bootstyle: Optional[BootstyleArg] = ...,
    ) -> None: ...

    def configure(self, cnf: Any = ..., *, bootstyle: Optional[BootstyleArg] = ..., **kwargs: Any) -> Any: ...

    config = configure


class Panedwindow(_ttk.Panedwindow):
    """TTK Panedwindow widget with ttkbootstrap theming support.

    A container widget that stacks widgets in resizable panes. Users can
    drag separators to resize panes.

    Args:
        master: Parent widget.
        class_: Widget class name for styling.
        cursor: Cursor to display when mouse is over the widget.
        height: Height of the panedwindow.
        name: Widget name.
        orient: Orientation of panes (horizontal or vertical).
        style: Custom ttk style name.
        takefocus: Whether widget accepts focus during keyboard traversal.
        width: Width of the panedwindow.
        bootstyle: ttkbootstrap style keywords for theming (e.g., 'info', 'dark').
                   Can be a string or tuple of keywords. Use this instead of 'style' for
                   ttkbootstrap theming.
    """

    def __init__(
            self,
            master: Any = ...,
            *,
            class_: str = ...,
            cursor: str = ...,
            height: int = ...,
            name: str = ...,
            orient: Any = ...,
            style: str = ...,
            takefocus: Any = ...,
            width: int = ...,
            bootstyle: Optional[BootstyleArg] = ...,
    ) -> None: ...

    def configure(self, cnf: Any = ..., *, bootstyle: Optional[BootstyleArg] = ..., **kwargs: Any) -> Any: ...

    config = configure


class Progressbar(_ttk.Progressbar):
    """TTK Progressbar widget with ttkbootstrap theming support.

    A widget that shows progress of a long operation. Can operate in
    determinate or indeterminate mode.

    Args:
        master: Parent widget.
        class_: Widget class name for styling.
        cursor: Cursor to display when mouse is over the widget.
        length: Length of the progress bar.
        maximum: Maximum value for the progress bar.
        mode: Mode of operation (determinate or indeterminate).
        name: Widget name.
        orient: Orientation of the bar (horizontal or vertical).
        phase: Current phase for indeterminate mode animation.
        style: Custom ttk style name.
        takefocus: Whether widget accepts focus during keyboard traversal.
        value: Current value of the progress bar.
        variable: Variable linked to the progress bar value.
        bootstyle: ttkbootstrap style keywords for theming (e.g., 'success.striped', 'warning').
                   Can be a string or tuple of keywords. Use this instead of 'style' for
                   ttkbootstrap theming.
    """

    def __init__(
            self,
            master: Any = ...,
            *,
            class_: str = ...,
            cursor: str = ...,
            length: Any = ...,
            maximum: float = ...,
            mode: Any = ...,
            name: str = ...,
            orient: Any = ...,
            phase: int = ...,
            style: str = ...,
            takefocus: Any = ...,
            value: float = ...,
            variable: Any = ...,
            bootstyle: Optional[BootstyleArg] = ...,
    ) -> None: ...

    def configure(self, cnf: Any = ..., *, bootstyle: Optional[BootstyleArg] = ..., **kwargs: Any) -> Any: ...

    config = configure


class Radiobutton(_ttk.Radiobutton):
    """TTK Radiobutton widget with ttkbootstrap theming support.

    A radiobutton widget that allows selection of one option from a group.
    Multiple radiobuttons share a variable and have different values.

    Args:
        master: Parent widget.
        class_: Widget class name for styling.
        command: Function or method to call when radiobutton is selected.
        compound: How to display text and image together (text, image, top, bottom, left, right, center, none).
        cursor: Cursor to display when mouse is over the widget.
        image: Image to display on the radiobutton.
        name: Widget name.
        padding: Extra space around the radiobutton contents.
        state: Widget state (normal, active, disabled, readonly).
        style: Custom ttk style name.
        takefocus: Whether widget accepts focus during keyboard traversal.
        text: Text to display next to the radiobutton.
        textvariable: Variable linked to the radiobutton text.
        underline: Index of character to underline in text.
        value: Value to set variable to when this radiobutton is selected.
        variable: Variable shared by radiobuttons in the same group.
        width: Width of the radiobutton in characters.
        bootstyle: ttkbootstrap style keywords for theming (e.g., 'danger.toolbutton', 'info').
                   Can be a string or tuple of keywords. Use this instead of 'style' for
                   ttkbootstrap theming.
    """

    def __init__(
            self,
            master: Any = ...,
            *,
            class_: str = ...,
            command: Any = ...,
            compound: Any = ...,
            cursor: str = ...,
            image: Any = ...,
            name: str = ...,
            padding: Any = ...,
            state: str = ...,
            style: str = ...,
            takefocus: Any = ...,
            text: Any = ...,
            textvariable: Any = ...,
            underline: int = ...,
            value: Any = ...,
            variable: Any = ...,
            width: Any = ...,
            bootstyle: Optional[BootstyleArg] = ...,
    ) -> None: ...

    def configure(self, cnf: Any = ..., *, bootstyle: Optional[BootstyleArg] = ..., **kwargs: Any) -> Any: ...

    config = configure


class Scale(_ttk.Scale):
    """TTK Scale widget with ttkbootstrap theming support.

    A slider widget that allows the user to select a numeric value from
    a range by dragging a slider.

    Args:
        master: Parent widget.
        class_: Widget class name for styling.
        command: Function or method to call when value changes.
        cursor: Cursor to display when mouse is over the widget.
        from_: Minimum value of the scale.
        length: Length of the scale widget.
        name: Widget name.
        orient: Orientation of the scale (horizontal or vertical).
        state: Widget state (normal, disabled, readonly).
        style: Custom ttk style name.
        takefocus: Whether widget accepts focus during keyboard traversal.
        to: Maximum value of the scale.
        value: Current value of the scale.
        variable: Variable linked to the scale value.
        bootstyle: ttkbootstrap style keywords for theming (e.g., 'info', 'success').
                   Can be a string or tuple of keywords. Use this instead of 'style' for
                   ttkbootstrap theming.
    """

    def __init__(
            self,
            master: Any = ...,
            *,
            class_: str = ...,
            command: Any = ...,
            cursor: str = ...,
            from_: float = ...,
            length: Any = ...,
            name: str = ...,
            orient: Any = ...,
            state: str = ...,
            style: str = ...,
            takefocus: Any = ...,
            to: float = ...,
            value: float = ...,
            variable: Any = ...,
            bootstyle: Optional[BootstyleArg] = ...,
    ) -> None: ...

    def configure(self, cnf: Any = ..., *, bootstyle: Optional[BootstyleArg] = ..., **kwargs: Any) -> Any: ...

    config = configure


class Scrollbar(_ttk.Scrollbar):
    """TTK Scrollbar widget with ttkbootstrap theming support.

    A scrollbar widget used to scroll other widgets such as listboxes,
    canvases, and text widgets.

    Args:
        master: Parent widget.
        class_: Widget class name for styling.
        command: Command to call when scrollbar is moved.
        cursor: Cursor to display when mouse is over the widget.
        name: Widget name.
        orient: Orientation of the scrollbar (horizontal or vertical).
        style: Custom ttk style name.
        takefocus: Whether widget accepts focus during keyboard traversal.
        bootstyle: ttkbootstrap style keywords for theming (e.g., 'primary.round', 'danger').
                   Can be a string or tuple of keywords. Use this instead of 'style' for
                   ttkbootstrap theming.
    """

    def __init__(
            self,
            master: Any = ...,
            *,
            class_: str = ...,
            command: Any = ...,
            cursor: str = ...,
            name: str = ...,
            orient: Any = ...,
            style: str = ...,
            takefocus: Any = ...,
            bootstyle: Optional[BootstyleArg] = ...,
    ) -> None: ...

    def configure(self, cnf: Any = ..., *, bootstyle: Optional[BootstyleArg] = ..., **kwargs: Any) -> Any: ...

    config = configure


class Separator(_ttk.Separator):
    """TTK Separator widget with ttkbootstrap theming support.

    A separator widget that displays a horizontal or vertical line.
    Used to visually separate groups of widgets.

    Args:
        master: Parent widget.
        class_: Widget class name for styling.
        cursor: Cursor to display when mouse is over the widget.
        name: Widget name.
        orient: Orientation of the separator (horizontal or vertical).
        style: Custom ttk style name.
        takefocus: Whether widget accepts focus during keyboard traversal.
        bootstyle: ttkbootstrap style keywords for theming (e.g., 'primary', 'secondary').
                   Can be a string or tuple of keywords. Use this instead of 'style' for
                   ttkbootstrap theming.
    """

    def __init__(
            self,
            master: Any = ...,
            *,
            class_: str = ...,
            cursor: str = ...,
            name: str = ...,
            orient: Any = ...,
            style: str = ...,
            takefocus: Any = ...,
            bootstyle: Optional[BootstyleArg] = ...,
    ) -> None: ...

    def configure(self, cnf: Any = ..., *, bootstyle: Optional[BootstyleArg] = ..., **kwargs: Any) -> Any: ...

    config = configure


class Sizegrip(_ttk.Sizegrip):
    """TTK Sizegrip widget with ttkbootstrap theming support.

    A grip widget that allows the user to resize the containing window
    by dragging. Typically placed in the bottom-right corner.

    Args:
        master: Parent widget.
        class_: Widget class name for styling.
        cursor: Cursor to display when mouse is over the widget.
        name: Widget name.
        style: Custom ttk style name.
        takefocus: Whether widget accepts focus during keyboard traversal.
        bootstyle: ttkbootstrap style keywords for theming (e.g., 'primary', 'secondary').
                   Can be a string or tuple of keywords. Use this instead of 'style' for
                   ttkbootstrap theming.
    """

    def __init__(
            self,
            master: Any = ...,
            *,
            class_: str = ...,
            cursor: str = ...,
            name: str = ...,
            style: str = ...,
            takefocus: Any = ...,
            bootstyle: Optional[BootstyleArg] = ...,
    ) -> None: ...

    def configure(self, cnf: Any = ..., *, bootstyle: Optional[BootstyleArg] = ..., **kwargs: Any) -> Any: ...

    config = configure


class Spinbox(_ttk.Spinbox):
    """TTK Spinbox widget with ttkbootstrap theming support.

    A spinbox widget that allows the user to select a value by typing or
    using up/down arrows. Can work with numeric ranges or value lists.

    Args:
        master: Parent widget.
        background: Background color of the entry field.
        class_: Widget class name for styling.
        command: Function or method to call when value changes.
        cursor: Cursor to display when mouse is over the widget.
        exportselection: Whether to export selection to X selection.
        font: Font for the entry text.
        foreground: Foreground (text) color of the entry field.
        format: Format string for numeric values.
        from_: Minimum numeric value.
        increment: Step size for numeric values.
        invalidcommand: Command to call when validation fails.
        justify: Text justification (left, center, or right).
        name: Widget name.
        show: Character to display instead of actual characters.
        state: Widget state (normal, readonly, disabled).
        style: Custom ttk style name.
        takefocus: Whether widget accepts focus during keyboard traversal.
        textvariable: Variable linked to the spinbox value.
        to: Maximum numeric value.
        validate: When to validate (none, focus, focusin, focusout, key, all).
        validatecommand: Command to call to validate input.
        values: List of values to cycle through (alternative to from_/to).
        width: Width of the spinbox in characters.
        wrap: Whether to wrap around at min/max values.
        xscrollcommand: Command to call when entry x-view changes.
        bootstyle: ttkbootstrap style keywords for theming (e.g., 'info', 'success').
                   Can be a string or tuple of keywords. Use this instead of 'style' for
                   ttkbootstrap theming.
    """

    def __init__(
            self,
            master: Any = ...,
            *,
            background: str = ...,
            class_: str = ...,
            command: Any = ...,
            cursor: str = ...,
            exportselection: bool = ...,
            font: Any = ...,
            foreground: str = ...,
            format: str = ...,
            from_: float = ...,
            increment: float = ...,
            invalidcommand: Any = ...,
            justify: Any = ...,
            name: str = ...,
            show: Any = ...,
            state: str = ...,
            style: str = ...,
            takefocus: Any = ...,
            textvariable: Any = ...,
            to: float = ...,
            validate: Any = ...,
            validatecommand: Any = ...,
            values: Any = ...,
            width: int = ...,
            wrap: bool = ...,
            xscrollcommand: Any = ...,
            bootstyle: Optional[BootstyleArg] = ...,
    ) -> None: ...

    def configure(self, cnf: Any = ..., *, bootstyle: Optional[BootstyleArg] = ..., **kwargs: Any) -> Any: ...

    config = configure


class Treeview(_ttk.Treeview):
    """TTK Treeview widget with ttkbootstrap theming support.

    A hierarchical, multi-column data display widget. Can display data
    in tree or table format with selectable items.

    Args:
        master: Parent widget.
        class_: Widget class name for styling.
        columns: List of column identifiers.
        cursor: Cursor to display when mouse is over the widget.
        displaycolumns: List of columns to display (subset of columns).
        height: Height of the widget in rows.
        name: Widget name.
        padding: Extra space inside the widget.
        selectmode: Selection mode (extended, browse, or none).
        show: Which elements to display (tree, headings, or both).
        style: Custom ttk style name.
        takefocus: Whether widget accepts focus during keyboard traversal.
        xscrollcommand: Command to call when tree x-view changes.
        yscrollcommand: Command to call when tree y-view changes.
        bootstyle: ttkbootstrap style keywords for theming (e.g., 'primary', 'info').
                   Can be a string or tuple of keywords. Use this instead of 'style' for
                   ttkbootstrap theming.
    """

    def __init__(
            self,
            master: Any = ...,
            *,
            class_: str = ...,
            columns: Any = ...,
            cursor: str = ...,
            displaycolumns: Any = ...,
            height: int = ...,
            name: str = ...,
            padding: Any = ...,
            selectmode: Any = ...,
            show: Any = ...,
            style: str = ...,
            takefocus: Any = ...,
            xscrollcommand: Any = ...,
            yscrollcommand: Any = ...,
            bootstyle: Optional[BootstyleArg] = ...,
    ) -> None: ...

    def configure(self, cnf: Any = ..., *, bootstyle: Optional[BootstyleArg] = ..., **kwargs: Any) -> Any: ...

    config = configure


class OptionMenu(_ttk.OptionMenu):
    """TTK OptionMenu widget with ttkbootstrap theming support.

    A dropdown menu widget that displays one selected value and allows
    selection from a list of options.

    Args:
        master: Parent widget.
        variable: Variable to link to the selected value.
        default: Default value to display.
        *values: Variable number of option values for the menu.
        style: Custom ttk style name.
        direction: Where to display the menu relative to button (above, below, left, right, flush).
        command: Function or method to call when selection changes.
        bootstyle: ttkbootstrap style keywords for theming (e.g., 'primary.outline', 'success').
                   Can be a string or tuple of keywords. Use this instead of 'style' for
                   ttkbootstrap theming.
    """

    def __init__(
            self,
            master: Any,
            variable: Any,
            default: Any = ...,
            *values: Any,
            style: str = ...,
            direction: Any = ...,
            command: Any = ...,
            bootstyle: Optional[BootstyleArg] = ...,
    ) -> None: ...

    def configure(self, cnf: Any = ..., *, bootstyle: Optional[BootstyleArg] = ..., **kwargs: Any) -> Any: ...

    config = configure


# TK widgets with autostyle parameter
class TkFrame(_tkFrame):
    """Tkinter Frame widget with ttkbootstrap theming support.

    A container widget that groups other tk widgets. Unlike ttk.Frame,
    this is the legacy tk.Frame widget with ttkbootstrap theming.

    Args:
        master: Parent widget.
        cnf: Configuration dictionary.
        background: Background color of the frame.
        bd: Border width (alias for borderwidth).
        bg: Background color (alias for background).
        border: Border width (alias for borderwidth).
        borderwidth: Width of the border around the frame.
        class_: Widget class name.
        colormap: Colormap to use for the frame.
        container: Whether frame is a container for embedding.
        cursor: Cursor to display when mouse is over the widget.
        height: Height of the frame.
        highlightbackground: Color of focus highlight when widget does not have focus.
        highlightcolor: Color of focus highlight when widget has focus.
        highlightthickness: Width of focus highlight border.
        name: Widget name.
        padx: Horizontal padding inside the frame.
        pady: Vertical padding inside the frame.
        relief: 3D effect for the border (flat, raised, sunken, groove, ridge).
        takefocus: Whether widget accepts focus during keyboard traversal.
        visual: Visual information.
        width: Width of the frame.
        autostyle: If True (default), applies ttkbootstrap theme styling automatically.
                   Set to False to disable automatic theming and use custom styling.
    """

    def __init__(
            self,
            master: Any = ...,
            cnf: Optional[dict[str, Any]] = ...,
            *,
            background: str = ...,
            bd: Any = ...,
            bg: str = ...,
            border: Any = ...,
            borderwidth: Any = ...,
            class_: str = ...,
            colormap: Any = ...,
            container: bool = ...,
            cursor: str = ...,
            height: Any = ...,
            highlightbackground: str = ...,
            highlightcolor: str = ...,
            highlightthickness: Any = ...,
            name: str = ...,
            padx: Any = ...,
            pady: Any = ...,
            relief: str = ...,
            takefocus: Any = ...,
            visual: Any = ...,
            width: Any = ...,
            autostyle: bool = ...,
    ) -> None: ...


class Tk(_tkTk):
    """Main tkinter root window with ttkbootstrap theming support.

    The root window is the main application window and must be created before
    any other widgets. It provides the main event loop and window management.

    Args:
        screenName: Name of the X11 screen to use.
        baseName: Base name for the application.
        className: Class name for the application (used for resource lookups).
        useTk: Whether to initialize the Tk subsystem.
        sync: Whether to execute X server commands synchronously.
        use: ID of window to embed application within.
        autostyle: If True (default), applies ttkbootstrap theme styling automatically.
                   Set to False to disable automatic theming and use custom styling.
    """

    def __init__(
            self,
            screenName: Optional[str] = ...,
            baseName: Optional[str] = ...,
            className: str = ...,
            useTk: bool = ...,
            sync: bool = ...,
            use: Optional[str] = ...,
            *,
            autostyle: bool = ...,
    ) -> None: ...


class Menu(_tkMenu):
    """Tkinter Menu widget with ttkbootstrap theming support.

    A menu widget that displays a list of choices. Menus can be used as menubars,
    popup menus, or option menus.

    Args:
        master: Parent widget.
        cnf: Configuration dictionary.
        activebackground: Background color when menu item is active.
        activeborderwidth: Border width of active menu items.
        activeforeground: Foreground color when menu item is active.
        background: Background color of the menu.
        bd: Border width (alias for borderwidth).
        bg: Background color (alias for background).
        border: Border width (alias for borderwidth).
        borderwidth: Width of the border around the menu.
        cursor: Cursor to display when mouse is over the widget.
        disabledforeground: Foreground color for disabled menu items.
        fg: Foreground color (alias for foreground).
        font: Font for menu item text.
        foreground: Foreground color of the menu.
        name: Widget name.
        postcommand: Command to call before menu is posted.
        relief: 3D effect for the border (flat, raised, sunken, groove, ridge).
        selectcolor: Color of selection indicator for check/radio buttons.
        takefocus: Whether widget accepts focus during keyboard traversal.
        tearoff: Whether menu can be torn off (0 or 1).
        tearoffcommand: Command to call when menu is torn off.
        title: Title for torn-off menu window.
        type: Type of menu (menubar, tearoff, or normal).
        autostyle: If True (default), applies ttkbootstrap theme styling automatically.
                   Set to False to disable automatic theming and use custom styling.
    """

    def __init__(
            self,
            master: Any = ...,
            cnf: Optional[dict[str, Any]] = ...,
            *,
            activebackground: str = ...,
            activeborderwidth: Any = ...,
            activeforeground: str = ...,
            background: str = ...,
            bd: Any = ...,
            bg: str = ...,
            border: Any = ...,
            borderwidth: Any = ...,
            cursor: str = ...,
            disabledforeground: str = ...,
            fg: str = ...,
            font: Any = ...,
            foreground: str = ...,
            name: str = ...,
            postcommand: Any = ...,
            relief: str = ...,
            selectcolor: str = ...,
            takefocus: Any = ...,
            tearoff: Any = ...,
            tearoffcommand: Any = ...,
            title: str = ...,
            type: str = ...,
            autostyle: bool = ...,
    ) -> None: ...


class Text(_tkText):
    """Tkinter Text widget with ttkbootstrap theming support.

    A text widget that displays multiple lines of text with support for
    formatting, tags, marks, and embedded images and windows.

    Args:
        master: Parent widget.
        cnf: Configuration dictionary.
        autoseparators: Whether to automatically insert undo separators.
        background: Background color of the text widget.
        bd: Border width (alias for borderwidth).
        bg: Background color (alias for background).
        blockcursor: Whether to use a block cursor instead of an I-beam.
        borderwidth: Width of the border around the widget.
        cursor: Cursor to display when mouse is over the widget.
        endline: Last line to display (for partial text display).
        exportselection: Whether to export selection to X selection.
        fg: Foreground color (alias for foreground).
        font: Font for the text.
        foreground: Foreground (text) color.
        height: Height of the widget in lines.
        highlightbackground: Color of focus highlight when widget does not have focus.
        highlightcolor: Color of focus highlight when widget has focus.
        highlightthickness: Width of focus highlight border.
        inactiveselectbackground: Background color for selection when widget is inactive.
        insertbackground: Color of the insertion cursor.
        insertborderwidth: Width of border around insertion cursor.
        insertofftime: Milliseconds the insertion cursor is off during blink cycle.
        insertontime: Milliseconds the insertion cursor is on during blink cycle.
        insertwidth: Width of the insertion cursor.
        maxundo: Maximum number of undo operations (-1 for unlimited).
        name: Widget name.
        padx: Extra horizontal space around the text.
        pady: Extra vertical space around the text.
        relief: 3D effect for the border (flat, raised, sunken, groove, ridge).
        selectbackground: Background color for selected text.
        selectborderwidth: Width of border around selected text.
        selectforeground: Foreground color for selected text.
        setgrid: Whether to enable gridded geometry management.
        spacing1: Extra space above each line.
        spacing2: Extra space between wrapped lines.
        spacing3: Extra space below each line.
        startline: First line to display (for partial text display).
        state: Widget state (normal or disabled).
        tabs: Tab stop positions.
        tabstyle: Tab style (tabular or wordprocessor).
        takefocus: Whether widget accepts focus during keyboard traversal.
        undo: Whether to enable undo/redo functionality.
        width: Width of the widget in characters.
        wrap: Line wrapping mode (none, char, or word).
        xscrollcommand: Command to call when text x-view changes.
        yscrollcommand: Command to call when text y-view changes.
        autostyle: If True (default), applies ttkbootstrap theme styling automatically.
                   Set to False to disable automatic theming and use custom styling.
    """

    def __init__(
            self,
            master: Any = ...,
            cnf: Optional[dict[str, Any]] = ...,
            *,
            autoseparators: bool = ...,
            background: str = ...,
            bd: Any = ...,
            bg: str = ...,
            blockcursor: bool = ...,
            borderwidth: Any = ...,
            cursor: str = ...,
            endline: Any = ...,
            exportselection: bool = ...,
            fg: str = ...,
            font: Any = ...,
            foreground: str = ...,
            height: Any = ...,
            highlightbackground: str = ...,
            highlightcolor: str = ...,
            highlightthickness: Any = ...,
            inactiveselectbackground: str = ...,
            insertbackground: str = ...,
            insertborderwidth: Any = ...,
            insertofftime: int = ...,
            insertontime: int = ...,
            insertwidth: Any = ...,
            maxundo: int = ...,
            name: str = ...,
            padx: Any = ...,
            pady: Any = ...,
            relief: str = ...,
            selectbackground: str = ...,
            selectborderwidth: Any = ...,
            selectforeground: str = ...,
            setgrid: bool = ...,
            spacing1: Any = ...,
            spacing2: Any = ...,
            spacing3: Any = ...,
            startline: Any = ...,
            state: str = ...,
            tabs: Any = ...,
            tabstyle: str = ...,
            takefocus: Any = ...,
            undo: bool = ...,
            width: Any = ...,
            wrap: str = ...,
            xscrollcommand: Any = ...,
            yscrollcommand: Any = ...,
            autostyle: bool = ...,
    ) -> None: ...


class Canvas(_tkCanvas):
    """Tkinter Canvas widget with ttkbootstrap theming support.

    A canvas widget manages a 2D collection of graphical objects such as
    lines, circles, images, and other widgets.

    Args:
        master: Parent widget.
        cnf: Configuration dictionary.
        background: Background color of the canvas.
        bd: Border width (alias for borderwidth).
        bg: Background color (alias for background).
        border: Border width (alias for borderwidth).
        borderwidth: Width of the border around the canvas.
        closeenough: How close the mouse must be to an item for it to be considered inside.
        confine: Whether to constrain the canvas view to the scroll region.
        cursor: Cursor to display when mouse is over the widget.
        height: Height of the canvas.
        highlightbackground: Color of focus highlight when widget does not have focus.
        highlightcolor: Color of focus highlight when widget has focus.
        highlightthickness: Width of focus highlight border.
        insertbackground: Color of insertion cursor.
        insertborderwidth: Width of border around insertion cursor.
        insertofftime: Milliseconds the insertion cursor is off during blink cycle.
        insertontime: Milliseconds the insertion cursor is on during blink cycle.
        insertwidth: Width of insertion cursor.
        name: Widget name.
        offset: Offset for stipple patterns.
        relief: 3D effect for the border (flat, raised, sunken, groove, ridge).
        scrollregion: Tuple (left, top, right, bottom) defining scrollable area.
        selectbackground: Background color for selected items.
        selectborderwidth: Width of border around selected items.
        selectforeground: Foreground color for selected items.
        state: Widget state (normal or disabled).
        takefocus: Whether widget accepts focus during keyboard traversal.
        width: Width of the canvas.
        xscrollcommand: Command to call when canvas x-view changes.
        xscrollincrement: Increment for horizontal scrolling.
        yscrollcommand: Command to call when canvas y-view changes.
        yscrollincrement: Increment for vertical scrolling.
        autostyle: If True (default), applies ttkbootstrap theme styling automatically.
                   Set to False to disable automatic theming and use custom styling.
    """

    def __init__(
            self,
            master: Any = ...,
            cnf: Optional[dict[str, Any]] = ...,
            *,
            background: str = ...,
            bd: Any = ...,
            bg: str = ...,
            border: Any = ...,
            borderwidth: Any = ...,
            closeenough: float = ...,
            confine: bool = ...,
            cursor: str = ...,
            height: Any = ...,
            highlightbackground: str = ...,
            highlightcolor: str = ...,
            highlightthickness: Any = ...,
            insertbackground: str = ...,
            insertborderwidth: Any = ...,
            insertofftime: int = ...,
            insertontime: int = ...,
            insertwidth: Any = ...,
            name: str = ...,
            offset: Any = ...,
            relief: str = ...,
            scrollregion: Any = ...,
            selectbackground: str = ...,
            selectborderwidth: Any = ...,
            selectforeground: str = ...,
            state: str = ...,
            takefocus: Any = ...,
            width: Any = ...,
            xscrollcommand: Any = ...,
            xscrollincrement: Any = ...,
            yscrollcommand: Any = ...,
            yscrollincrement: Any = ...,
            autostyle: bool = ...,
    ) -> None: ...


# Constant re-exported by the widgets module
M: int

__all__ = [
    # Tk exports
    "Tk",
    "Menu",
    "Text",
    "Canvas",
    "TkFrame",
    "Variable",
    "StringVar",
    "IntVar",
    "BooleanVar",
    "DoubleVar",
    "PhotoImage",

    # TTK exports
    "Button",
    "Checkbutton",
    "Combobox",
    "Entry",
    "Frame",
    "Labelframe",
    "Label",
    "Menubutton",
    "Notebook",
    "Panedwindow",
    "Progressbar",
    "Radiobutton",
    "Scale",
    "Scrollbar",
    "Separator",
    "Sizegrip",
    "Spinbox",
    "Treeview",
    "OptionMenu",

    # ttkbootstrap
    "Bootstyle",
    "Style",
    "Toplevel",
    "Window",
    "DateEntry",
    "Floodgauge",
    "FloodgaugeLegacy",
    "LabeledScale",
    "Meter",
    "M",
]
