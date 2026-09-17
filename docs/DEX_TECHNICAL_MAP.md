# Samsung DeX Technical Map for PhoneDesk

## Test environment

- Device: Samsung Galaxy S25 Ultra (`SM-S938B`)
- Android: 16 / One UI 8.5
- Transport: wireless ADB
- scrcpy: 4.1

## Native Samsung components discovered

Samsung DeX on this device is not exposed as one standalone `dex` app. The desktop experience is distributed across One UI Home, SystemUI and Android window-management services.

Key components observed through ADB:

- `com.sec.android.app.launcher/com.honeyspace.dexservice.SecondaryLauncher`
  - Handles `MAIN` + `SECONDARY_HOME`.
  - Becomes the HOME task automatically on the scrcpy secondary display.
- `com.sec.android.app.launcher/com.honeyspace.dexservice.DesktopModeTile`
  - Connected to Samsung's Desktop Mode / Wireless DeX quick setting.
- `DexTaskbarWindow`
  - Native Samsung desktop taskbar created on the secondary display.
- `NavigationBar<displayId>`
  - Per-display Samsung/Android navigation surface.
- `com.android.systemui.dextouchpad.activity.TouchpadActivity`
  - DeX-specific SystemUI component.

## Reproduced native desktop recipe

The following scrcpy virtual-display profile caused Samsung to create `SecondaryLauncher`, `DexTaskbarWindow`, wallpaper and a display-specific navigation bar automatically:

```text
--new-display=1600x900/160
--flex-display
--keep-active
--display-ime-policy=local
--mouse=sdk
--keyboard=sdk
--audio-source=output
--max-fps=60
```

The resulting virtual display was observed with trusted/presentation/system-decoration flags and its own focus. No root access was required.

## Application discovery

`pm list packages -3` is not sufficient because it excludes Samsung and system applications.

PhoneDesk now discovers launchable applications from Android's launcher resolver:

```text
cmd package query-activities -a android.intent.action.MAIN -c android.intent.category.LAUNCHER
```

On the test phone this returned 342 launchable activities during investigation.

## Important restrictions

- Starting `SecondaryLauncher` manually with `am start --display ...` from the ADB shell can fail with a `SecurityException` because Samsung protects display/task management APIs.
- This is not required for the primary approach: Android launches `SECONDARY_HOME` automatically when the virtual display has the proper characteristics.
- Samsung's internal `DexController` did not identify the scrcpy display as a physical external DeX monitor; nevertheless One UI created the native secondary launcher and DeX taskbar on it.

## Architecture decision

PhoneDesk will use Samsung's native secondary-display UI when the connected Samsung device provides it. We do not copy Samsung source code, trademarks, or proprietary UI assets.

The custom floating PhoneDesk navigation bar is retired from the primary path. PhoneDesk remains responsible for connection, display creation, compatibility handling and fallback behavior.

## Next validation

1. Verify mouse and keyboard interaction with the native taskbar.
2. Verify Samsung app drawer shows the full application set.
3. Verify launching multiple apps and freeform/multi-window behavior.
4. Add automatic device discovery and reconnect.
5. Package the desktop build, then design the browser/link version.
