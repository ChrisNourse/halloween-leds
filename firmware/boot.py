"""USB descriptor changes take effect after a physical reset."""
import usb_cdc
import usb_hid
import usb_midi
import os
import storage
import supervisor

usb_hid.disable()
usb_midi.disable()
supervisor.runtime.rgb_status_brightness = 8
# Normal mode gives OTA filesystem ownership even with USB power/data attached.
# The host tool creates this marker for a temporary USB disk installation.
try:
    os.stat("/USB_INSTALL")
    install_mode = True
except OSError:
    install_mode = False
if install_mode:
    usb_cdc.enable(console=True, data=False)
else:
    storage.disable_usb_drive()
    usb_cdc.enable(console=True, data=True)
