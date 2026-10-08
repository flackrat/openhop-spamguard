# openHop Repeater: prerequisites and fresh install

_Native install on a Raspberry Pi · October 2026_

## What you need

To run openHop Repeater natively you need a Raspberry Pi running a Debian-based OS with systemd, Python 3.10 or newer, a supported SX1262 LoRa radio, and an antenna setup that is legal where you live ([install docs](https://docs.openhop.dev/projects/openhop-repeater/installation/)).

| Item | Requirement | Notes |
|---|---|---|
| Computer | Raspberry Pi with SPI and GPIO (or any Linux host for USB/network radios) | A Pi 3 or newer is comfortable; SpamGuard adds about 40 MB of memory |
| Operating system | Debian or Ubuntu-style Linux with APT and systemd | Raspberry Pi OS Lite is the simplest choice |
| Python | 3.10 or newer | Current Raspberry Pi OS includes it |
| Radio | SX1262-class: a SPI HAT, a CH341 USB-SPI adapter, an openHop Modem (USB or network), or a KISS serial modem | Named presets include PiMesh 1W, Frequency Labs meshadv / meshadv-mini, Zebra, NebraHat, Femtofox, RAK6421/RAK13300, Zindello UltraPeater, Waveshare SX1262 SPI HAT ([hardware docs](https://docs.openhop.dev/projects/openhop-repeater/hardware-setup/)) |
| Not supported | UART-only HATs, SX1302/SX1303 concentrator boards | |
| Antenna | An antenna for your band, fitted before any transmitting | Never transmit without an antenna |
| Network | Wired or Wi-Fi LAN, with a fixed IP or DHCP reservation for the Pi | Keep port 8000 off the public internet |
| Your PC | An SSH client (PuTTY on Windows) and a browser | |

**Radio limits (UK example).** The usual UK MeshCore band, 869.40–869.65 MHz, allows 500 mW ERP with a 10% duty cycle ([summary](https://en.wikipedia.org/wiki/Short-range_device)). ERP includes antenna gain, so a high-power radio plus a gain antenna can exceed it: keep transmitter power + antenna gain (dBd) − cable loss at or below 27 dBm. In the UK, check Ofcom's current IR2030 interface requirement before choosing power. Elsewhere, check your own regulator's rules and your local mesh's frequency.

## Prepare the Pi

A freshly flashed, updated Pi with SSH, SPI and the right time zone takes about 20 minutes.

1. **Flash the card.** In Raspberry Pi Imager choose Raspberry Pi OS Lite (64-bit). Under OS customisation set a hostname, a username and password, Wi-Fi if needed, your time zone and keyboard layout, and tick **Enable SSH**.
2. **Fit the radio HAT and antenna** with the Pi powered off, then boot it.
3. **Find the Pi's address.** Look in your router's list of connected devices for the hostname you chose, or try `<hostname>.local`. Then reserve that IP for the Pi in your router's DHCP settings so the dashboard address doesn't change.
4. **Log in** (on your PC):

    ```
    ssh <user>@<pi-ip>
    ```

    Throughout this guide, `<user>` is the username you set in Imager and `<pi-ip>` is the Pi's IP address (or `<hostname>.local`). Type your own values without the `< >`. Once logged in, `hostname -I` shows the Pi's current IP.

5. **Update, install git, and enable SPI** (on the Pi):

    ```
    sudo apt update && sudo apt full-upgrade -y
    sudo apt install -y git
    sudo raspi-config nonint do_spi 0
    # your time zone; list them with: timedatectl list-timezones
    sudo timedatectl set-timezone Europe/London
    sudo timedatectl set-ntp true
    sudo reboot
    ```

6. **Check SPI after the reboot.** You should see a device such as `/dev/spidev0.0`:

    ```
    ls /dev/spidev*
    timedatectl
    ```

SPI is only needed for HATs on the Pi's GPIO pins. USB or network modems skip the SPI step.

## Install openHop

The openHop docs follow the `dev` branch. For the stable release, leave out `--branch dev --single-branch`.

```
cd ~
git clone --branch dev --single-branch https://github.com/openhop-dev/openhop_repeater.git
cd openhop_repeater
sudo bash ./manage.sh install
```

The installer sets up:

| What | Where |
|---|---|
| Service user | `repeater` |
| Program and Python venv | `/opt/openhop_repeater` (venv in `/opt/openhop_repeater/venv`) |
| Config | `/etc/openhop_repeater/config.yaml` |
| Data (database, identity) | `/var/lib/openhop_repeater` |
| Logs | `/var/log/openhop_repeater` |
| Services | `openhop-repeater.service` and `openhop-plugin-manager.service` |

At the end the installer runs a radio setup wizard. If you skip it, the config starts with `radio_type: null` and the web setup page asks for the radio settings instead.

Keep the `~/openhop_repeater` folder. You need it for upgrades.

## First boot (setup wizard)

Open `http://<pi-ip>:8000/setup` in a browser. The wizard asks for:

1. **Repeater name.** This is what other people see on the mesh.
2. **Radio hardware.** Pick your HAT or board from the list.
3. **Radio preset.** Choose the one your local mesh uses, because every repeater nearby has to use the same settings. In the UK that is **EU/UK (Narrow)**: 869.618 MHz, SF8, BW 62.5 kHz, CR 8.
4. **Admin password.** Change it from the default.

Good habits for the first day:

- TX power defaults to 14 dBm. Raise it only if you need to, and keep power plus antenna gain within your local ERP limit (500 mW / 27 dBm in the UK).
- If you're unsure, start with `repeater.mode: no_tx` (listen only). Switch to normal repeating once you can see packets arriving.
- When reception works, run **CAD calibration** from the dashboard. Do it at a quiet time first for a baseline, then check it still hears known traffic.
- Change any other default passwords (guest/admin) under System > Configuration.

## Check it is working

```
sudo systemctl status openhop-repeater          # should say active (running)
sudo systemctl status openhop-plugin-manager
sudo journalctl -u openhop-repeater -n 100      # last 100 log lines
sudo journalctl -u openhop-repeater -f          # live log, Ctrl+C to stop
```

On the dashboard (`http://<pi-ip>:8000`), check that:

- the packet list updates as traffic arrives
- noise floor and RSSI readings look sensible
- neighbours start appearing after a few adverts

Back up your identity and config once it works. The identity key is what makes your repeater *your* repeater, so keep the copy somewhere safe:

```
sudo tar czf ~/openhop-backup-$(date +%F).tar.gz /etc/openhop_repeater /var/lib/openhop_repeater
```

Don't forward port 8000 on your router. Use a VPN (Tailscale, WireGuard) if you want to reach the dashboard from outside.

## Next steps: API token and SpamGuard

1. In the openHop dashboard, go to **System > Configuration > Access > API Tokens** and create a token named `spamguard`. Copy it straight away, because it is only shown once.
2. Follow the [SpamGuard install and troubleshooting guide](install-and-troubleshooting.md) from its first step. SpamGuard uses openHop's Python venv, so openHop must be installed first.

Treat the token like a password. If it has been pasted anywhere public, delete it and create a new one.

## openHop commands and troubleshooting

### Everyday commands

```
sudo systemctl restart openhop-repeater
sudo systemctl stop openhop-repeater
sudo journalctl -u openhop-repeater -u openhop-plugin-manager -n 100 --no-pager
sudo nano /etc/openhop_repeater/config.yaml     # then restart
```

### Upgrade

```
cd ~/openhop_repeater
git status --short --branch
git fetch origin
git switch dev
git pull --ff-only origin dev
sudo bash ./manage.sh upgrade
sudo systemctl status openhop-repeater openhop-plugin-manager
sudo journalctl -u openhop-repeater -u openhop-plugin-manager -n 100 --no-pager
```

After an openHop upgrade, SpamGuard puts its rules back within a minute. You don't need to reinstall it, but do reapply the speed fix below.

### Change radio settings

Use the dashboard: **System > Configuration > Radio > Radio Hardware**. You can also rerun the old wizard, but back up first:

```
sudo cp /etc/openhop_repeater/config.yaml ~/config.yaml.bak
cd ~/openhop_repeater && sudo bash setup-radio-config.sh /etc/openhop_repeater
sudo systemctl restart openhop-repeater
```

### Keep openHop fast on a small Pi

On a Pi 3 with a large packet database, openHop can sit at 100% CPU and fall minutes behind saving packets. Its dashboard and anything reading its packet list (such as SpamGuard) then run late. Two settings keep it quick.

**1. Keep 7 days of packet history instead of 31.** The long-term graphs come from a separate metrics file and are not affected.

```
sudo grep -n -A4 "retention:" /etc/openhop_repeater/config.yaml
sudo nano /etc/openhop_repeater/config.yaml
#   storage:
#     retention:
#       sqlite_cleanup_days: 7
sudo systemctl restart openhop-repeater
```

**2. Apply the packet-count speed fix.** Each time openHop saves a packet it recounts every stored packet, keeping the answer for only 3 seconds, although only the once-a-minute graphs use it. Keeping it for 60 seconds removes most of that work. If SpamGuard is installed, its installer offers this, or run `sudo bash /opt/openhop_spamguard/tune-openhop.sh`. Without SpamGuard:

```
F=$(sudo find /opt/openhop_repeater -path "*repeater/data_acquisition/sqlite_handler.py" | head -1)
echo "File: $F"
sudo grep -n "_cumulative_counts_ttl_sec = " "$F"     # should show 3.0
sudo sed -i 's/self._cumulative_counts_ttl_sec = 3.0/self._cumulative_counts_ttl_sec = 60.0/' "$F"
sudo grep -n "_cumulative_counts_ttl_sec = " "$F"     # should now show 60.0
sudo systemctl restart openhop-repeater
```

Run the block once; if the `File:` line is empty, stop. An openHop upgrade puts the old value back, so reapply it after upgrading. To undo, swap `60.0` and `3.0` in the `sed` line and restart.

To check how busy openHop is: `top -b -n1 | head -12` (the openHop `python` process should be well under 100%). To see what it is busy doing: `sudo /opt/openhop_repeater/venv/bin/pip install py-spy`, then `sudo /opt/openhop_repeater/venv/bin/py-spy dump --pid $(pgrep -f repeater.main)` and look at the threads marked `(active)`.

### Problems and fixes

| Symptom | Check / fix |
|---|---|
| Dashboard won't load | `sudo systemctl status openhop-repeater`. If it's failed, read the last 100 log lines for the error. Check you're using the Pi's current IP (`hostname -I`). |
| Log says no SPI device, or `ls /dev/spidev*` shows nothing | `sudo raspi-config nonint do_spi 0`, then `sudo reboot` |
| Radio not detected | Check the HAT is seated and the right hardware is chosen in Radio Hardware |
| Serial / USB modem permission denied | `sudo usermod -aG dialout repeater`, then restart the service |
| Hears nothing | Frequency, SF, BW and CR must exactly match your neighbours (UK: 869.618 / SF8 / 62.5 / CR8). Check the antenna is connected. |
| Times on packets are wrong | Set your time zone, e.g. `sudo timedatectl set-timezone Europe/London`, then check `timedatectl` (NTP should say active) |
| Pi slow or rebooting | `vcgencmd get_throttled` (0x0 is good). Use the official power supply. |
| Lost admin password | Reset it in `config.yaml`, or rerun setup (see the openHop docs) |

If you installed with Docker, the paths and commands are different. This guide covers the native install only.

---

This guide describes one way of setting up openHop and is not official openHop documentation; check the [openHop docs](https://docs.openhop.dev/) for the current instructions. Radio settings and power limits are the operator's responsibility. Provided "as is", without warranty. See the [Disclaimer](../README.md#disclaimer).
