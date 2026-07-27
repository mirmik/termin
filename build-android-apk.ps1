#!/usr/bin/env pwsh
# Build a Termin Android APK on Windows.

$ErrorActionPreference = "Stop"

& (Join-Path $PSScriptRoot "build-system\android-apk-wrapper.ps1") `
    -Product "android" `
    -Arguments $args

