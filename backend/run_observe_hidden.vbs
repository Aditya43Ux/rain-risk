Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")
sh.Run """" & fso.GetParentFolderName(WScript.ScriptFullName) & "\run_observe.bat""", 0, True
