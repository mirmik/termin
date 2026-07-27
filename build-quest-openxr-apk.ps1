#!/usr/bin/env pwsh
# Build the experimental Quest/OpenXR APK entry point on Windows.

$ErrorActionPreference = "Stop"

& (Join-Path $PSScriptRoot "build-system\android-apk-wrapper.ps1") `
    -Product "quest-openxr" `
    -Arguments $args

