Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "D:\Project\CapsWriter-Offline"
WshShell.Run """D:\Project\CapsWriter-Offline\CapsWriter-GUI.exe"" -m gui.main_window", 0, False
