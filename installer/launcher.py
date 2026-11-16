"""Einstiegspunkt für den Windows-Build (PyInstaller). Der Scan ist nur über die Oberfläche startbar."""
from claudios.app import main

raise SystemExit(main())