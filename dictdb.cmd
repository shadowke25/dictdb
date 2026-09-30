@echo off
rem dictdb global command shim: run `python -m dictdb` with this dir on PYTHONPATH.
rem Usage: add this file's dir to PATH, or copy this file into any PATH dir.
rem NOTE: keep this file ASCII-only. cmd.exe parses batch files in the ANSI
rem codepage (GBK on zh-CN Windows); UTF-8 Chinese comments here corrupt line
rem parsing and produce bogus "'xx' is not recognized" errors.
set "PYTHONIOENCODING=utf-8"
set "PYTHONPATH=%~dp0;%PYTHONPATH%"
python -m dictdb %*
