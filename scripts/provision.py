#!/usr/bin/env python3
"""Connect an old Samsung air conditioner to your Wi-Fi (AP-mode provisioning).

Some old Samsung AC Wi-Fi modules cannot be joined to a network over the air. If
your router has no WPS button, you provision the unit from a computer while it is
broadcasting its temporary setup network. This is a single, self-contained file
that uses only the Python standard library — nothing to install.

Quick start (interactive):
  1. Install Python 3 if you don't have it (https://www.python.org/downloads/).
  2. Put the unit in AP mode: on the remote, hold `Timer` for 4 seconds. It
     creates a Wi-Fi network named `SMARTAIRCON` (password `1111122222`).
  3. Connect the computer to the `SMARTAIRCON` network.
  4. Run:  python3 provision.py
     and enter your home Wi-Fi name and password when asked.
  5. When it prints "Done", the unit leaves AP mode and joins your Wi-Fi.
     Reconnect the computer to your normal network.

Advanced (non-interactive): see `python3 provision.py --help`.
"""
import argparse
import getpass
import os
import re
import socket
import ssl
import sys
import tempfile
import time
from xml.sax.saxutils import quoteattr

_DUID_RE = re.compile(r'DUID="([0-9A-Fa-f]{12})"')


def _format_mac(duid: str) -> str:
    d = duid.lower()
    return ":".join(d[i : i + 2] for i in range(0, 12, 2))

# The unit's address and port while it is broadcasting the SMARTAIRCON network.
AP_HOST = "192.168.1.254"
PORT = 2878

# Public Samsung AC14K client certificate, required for the mutual-TLS handshake.
# Embedded so this stays a single download-and-run file.
CLIENT_CERT = """\
Bag Attributes
    friendlyName: ac14k_m
    localKeyID: 54 69 6D 65 20 31 34 35 35 34 39 32 33 35 32 36 39 36
Key Attributes: <No Attributes>
-----BEGIN PRIVATE KEY-----
MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQDeXvhcsqRFWfQt
Qr2TGW+ePJzrKQVNOZmCGFXrBmOKa2gcZvXqDe71upkCmbXxDZbsqU1nFox6WtKy
za+JE1EaWIjVFV/D0hnnF+CA56851rFjAx7YYVtd9TwJYV1lSfJaQBU/ecUys0SX
lKZJtjIoJ/PyLREE79TjOqTxXMXnDpiAt3oiwApZMweJ5z2QViqtRepkI33GDgYc
LzamIengSG6WZkEUr2roY0il4aVXf3IRVRX+5cJ2L5462kFPKm/UnrXrSsrLwbF9
ltSlNA8FgpHN3d9ZyqB3MB46oGYyxYYU7a+/R3RAx0joNfVPFe8riQXQcoNEgalb
c8f7N4HPAgMBAAECggEABL80QA5UMWLNMpYlI9m8Jz2V//MdONvM6hkI5H57a34F
d+2+vCNWAYrdL1AGsUGgAidPDq9NimMb8lMvtxZhedV//kR5id2XTfaVhUrs06hA
myN66hWR9LyCbpTUgJAGi2Soz3US/5USFsZGknZANdk8fOP3ZAqWmc8rrDdVxivg
Z3qjiqgIZg24XsZmnK/QJejP4FLMqm6YUouH//u9xSKvTwkg89qxvygW9xNBNfi/
LrBHip/k8LnynKRE2odQWt74HcTjbZW4rxXrJ0tqDSIh8bUB23mRjFh1k4aKXnz3
Y/CDsfxvAutVi85/zyxYaIT6daP+PxvywwgjVhYHIQKBgQDyMxmGdi5kk3ePv0lM
lC28gVNhgKfhsXL8xIzcd/UM3eEK4baA+AKI9p6ifZ8g90NUJGuHxCp8/9yOKcmk
tY5toE45nH4fH9Z3j9NtWHMhXJDGWV+DjeiWmshbUqd7/OoIl1vig1npQqX+PXJR
pwDHnjkQbkyum4k8/IruHx813wKBgQDrCqK0rBkMaarr5eyOJ9BxhCej8i5kCzm7
XSaNgXtpBIQ4Y4r412M2JWaSLnDxlAc0iUhNGnIn4zkEP2HzX5JU4Yto9YAlRZnu
NQSvuVgyLiBCbS7WrRAlsNpTeCU3m+c5QNXBzBlHCiTdw3WS4bINOftsB3xnlJ+D
y/0YZozSEQKBgQCgWV5z3Dh40/0bSVyA+7WQENsgOWpsjOwBFyvfJvgxLZC5gJgw
qIIdJZH/KEY7MBj+UyJx/1jV6xudb2MVzjHeuHwxvj7t4kk+XRVwVlfa5YrgFvma
glBTrWQquf0ypE5Zo8PsomPbgAmf2hSepH9qqYFENJJGI6lnnBdq8WXbZwKBgQCR
p3ye5At9wrnWCB0pFwk4X4JFOd5/xukW8CnlBTmaId9iJmXHwYpM0q6Wpkr9mhNA
/lYc2eemSkxaEoE71Z0UFtVSzNiFwHUcxiRKVVyPdEAvigO9q2/XO5qAoXLG3ElV
FJWizD1Z5bJk7yycQlsZkTX6g0UX12VmwnHsvhhEUQKBgF0AVToAk+/OPxlA3N4A
Xn624Ktxzy/58NSLUfQ57AtL2zivoJzfmhUwgYkPsp+63Wklpcq7X7Q2NB7WscC4
rICqHxNow/KSzwuR6L3u/kewvlsrgTIM2Pp//+QdTK9GGU3HHAZKaNiB8m20k1Bs
NTANFxBk7alY0G7ZUhuzWkg6
-----END PRIVATE KEY-----
Bag Attributes
    friendlyName: ac14k_m
    localKeyID: 54 69 6D 65 20 31 34 35 35 34 39 32 33 35 32 36 39 36
subject=/C=KR/O=Samsung Electronics/CN=AC14K_M/emailAddress=AC14K_M@samsung.com
issuer=/C=KR/O=Samsung Electronics/CN=RemoteAccessCA(CE)
-----BEGIN CERTIFICATE-----
MIIDmzCCAoOgAwIBAgIBCTANBgkqhkiG9w0BAQUFADBIMQswCQYDVQQGEwJLUjEc
MBoGA1UECgwTU2Ftc3VuZyBFbGVjdHJvbmljczEbMBkGA1UEAwwSUmVtb3RlQWNj
ZXNzQ0EoQ0UpMCIYDzE5NjAwMTAxMDAwMDAwWhgPMjA2MDAxMDEwMDAwMDBaMGEx
CzAJBgNVBAYTAktSMRwwGgYDVQQKExNTYW1zdW5nIEVsZWN0cm9uaWNzMRAwDgYD
VQQDFAdBQzE0S19NMSIwIAYJKoZIhvcNAQkBFhNBQzE0S19NQHNhbXN1bmcuY29t
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA3l74XLKkRVn0LUK9kxlv
njyc6ykFTTmZghhV6wZjimtoHGb16g3u9bqZApm18Q2W7KlNZxaMelrSss2viRNR
GliI1RVfw9IZ5xfggOevOdaxYwMe2GFbXfU8CWFdZUnyWkAVP3nFMrNEl5SmSbYy
KCfz8i0RBO/U4zqk8VzF5w6YgLd6IsAKWTMHiec9kFYqrUXqZCN9xg4GHC82piHp
4EhulmZBFK9q6GNIpeGlV39yEVUV/uXCdi+eOtpBTypv1J6160rKy8GxfZbUpTQP
BYKRzd3fWcqgdzAeOqBmMsWGFO2vv0d0QMdI6DX1TxXvK4kF0HKDRIGpW3PH+zeB
zwIDAQABo3MwcTAdBgNVHQ4EFgQUXzEjosLzA6xbR1KAqnmAp3BNM6MwHwYDVR0j
BBgwFoAU/12TkC/BOF7xDaZZWJ+DGN6nMxcwDAYDVR0TBAUwAwEB/zAhBgNVHREE
GjAYggtzYW1zdW5nLmNvbYIJbG9jYWxob3N0MA0GCSqGSIb3DQEBBQUAA4IBAQBW
0mStlbdvrHqDJ+KOKVf0C/y9FKTODqo/6/wJNZeZ+8ezPza4nFq70MwQYTpSbZhz
5w8bQP9fwSAoa2Vki8ZwcSd85Vi2tHz9O4C7d7zBA3FU8AL3NoEMFv6OGWGPnTY5
mG/Hn+LxuwQddlysfbRDds1LBY8DBUJNAmIeeWqA5Eg8DW6xJUwHeXUElJpSXHW6
XGvpWgAhXqoIf6TirdCrPY6+IzV/FcuVtBDGi+JoxgrMfMLgLEVjeSY96DJinHgZ
RT0FkA5e06Z+fqHh9Btu+aed+kuGSmya/A5wStOkGeKEbezbbN2gtW07lN6VxX3J
OCgygA+hmnBVnRDA8Jzu
-----END CERTIFICATE-----
Bag Attributes
    friendlyName: CN=RemoteAccessCA(CE),O=Samsung Electronics,C=KR
subject=/C=KR/O=Samsung Electronics/CN=RemoteAccessCA(CE)
issuer=/C=KR/O=Samsung Electronics/CN=CECA
-----BEGIN CERTIFICATE-----
MIIDUTCCAjmgAwIBAgIBADANBgkqhkiG9w0BAQUFADA6MQswCQYDVQQGEwJLUjEc
MBoGA1UECgwTU2Ftc3VuZyBFbGVjdHJvbmljczENMAsGA1UEAwwEQ0VDQTAiGA8x
OTYwMDEwMTAwMDAwMFoYDzIwNjAwMTAxMDAwMDAwWjBIMQswCQYDVQQGEwJLUjEc
MBoGA1UECgwTU2Ftc3VuZyBFbGVjdHJvbmljczEbMBkGA1UEAwwSUmVtb3RlQWNj
ZXNzQ0EoQ0UpMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAtatz9GvV
qbV395Whnad9MC9TEOiXuwnw37QHvQUwOTFgc6AenX5SORfb4UTw+0ApFNba9DlY
Xx/K9E5b5DGasDVGGTn+z+6MPB7GuAjkP+WSRwHMjrHRNqrBOr1YJUw3SIbMkRoT
460k9AD9DQDBORRtGBGwcBw6BvdasA+/L3Q63aJ7pDoj3qxocdcgk/zFq0OrxFDL
PMTL7a+a9DS8G10K73XGgES0RBwwhlXXVuLUprD6RgbeLHFsPpIq5vzzEpAYMCF6
vkZKjDGEW7JVTgUu0E37niN3NQv1gIXlJusDH6RWfFQxENZsdFkT/l+kTuY283Ga
2Ei1HsW3Xpt88QIDAQABo1AwTjAdBgNVHQ4EFgQU/12TkC/BOF7xDaZZWJ+DGN6n
MxcwHwYDVR0jBBgwFoAURwF9jkihypJa2u6zRwKrZwRlACswDAYDVR0TBAUwAwEB
/zANBgkqhkiG9w0BAQUFAAOCAQEAZkjxN4O92e1RTaXx1mpazyT98sJVl46R51s1
CTPq35HVfTiBOAu0C5MR6a9vIIFJScy5h69VN4OwDDbMhe/k3m6EfAutlL7lRrre
OT853HJahxdavzaXJ7tcrI/yDJI0X5GbQ8W74mmDt2/5rXsaB+h+NrToGqf6Hvf/
m7ZhUnCAt0hhLmltxTVYS25s9KoiIH0rXOb9cqUFsmBMEG2pHWC5AiSc0cXJm+kU
3z0B2GS+4IjGdVr3FTPzzTXrpqq/X1cIVKAum5WfsFMS0CRvqTVNVwYg52n69T2B
NPCCEpp9rsIieZ58jsnc506Uc+1Vp+NmBI2A/ecypZxSb6v9gg==
-----END CERTIFICATE-----
Bag Attributes
    friendlyName: CN=CECA,O=Samsung Electronics,C=KR
subject=/C=KR/O=Samsung Electronics/CN=CECA
issuer=/C=KR/O=Samsung Electronics/CN=ROOTCA
-----BEGIN CERTIFICATE-----
MIIDRTCCAi2gAwIBAgIBBDANBgkqhkiG9w0BAQUFADA8MQswCQYDVQQGEwJLUjEc
MBoGA1UECgwTU2Ftc3VuZyBFbGVjdHJvbmljczEPMA0GA1UEAwwGUk9PVENBMCIY
DzE5NjAwMTAxMDAwMDAwWhgPMjA2MDAxMDEwMDAwMDBaMDoxCzAJBgNVBAYTAktS
MRwwGgYDVQQKDBNTYW1zdW5nIEVsZWN0cm9uaWNzMQ0wCwYDVQQDDARDRUNBMIIB
IjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAtv1WJJ7tTs/aa1ZZRjMPPLeb
n/Ev0Y28CSBj/6P031/veZSg/2z65QZUvPjv8MZnIgNoMpxMGbPPO4Dxj+QJthBk
WydWRPguPyE+w3U4SdayZXWpLZTpKfHco3CklFwEqZtG/wTxHD1oOvtT0e2g5c79
hNQt9lQ4Wwzqa3MvQd0JyeB4syy2zRLo5NjJZl1BVn2oTt4xGCjjtAXtAqqHEbEf
pcvB3hPdIpFe6M8zuN22kROKaQ5i4XP4CyEpbFlgKRcWBGQFX3I5f5TdD3Yw1Ril
OLLL9wFsJ+iWLka9tAIcJKCNOf48p7aXm6COFwmjtCNu4wjQozwi6cycKUgxNQID
AQABo1AwTjAdBgNVHQ4EFgQURwF9jkihypJa2u6zRwKrZwRlACswHwYDVR0jBBgw
FoAU7andrmFFrxYM8+93lrn/Fq47sXMwDAYDVR0TBAUwAwEB/zANBgkqhkiG9w0B
AQUFAAOCAQEATexseQBXSfUR7fFTFxq6aAvHWIN+h3QLeN1sq8KCM4fbdkH3lOUP
rKW3w1ag62bnJVNjT4xPtzH/DyrqlzQUPTb7S0PfIXt2mu/VURnrmuXidS2grNwv
eu10gURZaz9N2UZEhY7E80tUZwcjAV+YP8+x3/iRQSrWvcMma/r01eUnwrF4xaE9
EYtJ/jTRre8MpEH/lg06m+rZf9Lk/yhG6at0YnUAIytThqFV4Cj8T8jBX+KG8BCo
VyUsFyrO+D6X98gMdTZnLqC1P1iWuxyrOWZTgsf44f5GXzmLqe5KLPvkDb4MywTa
nXrSOPSkcIgvS6WYw2Rii+e6lfVzqmhAmg==
-----END CERTIFICATE-----
Bag Attributes
    friendlyName: CN=ROOTCA,O=Samsung Electronics,C=KR
subject=/C=KR/O=Samsung Electronics/CN=ROOTCA
issuer=/C=KR/O=Samsung Electronics/CN=ROOTCA
-----BEGIN CERTIFICATE-----
MIIDRzCCAi+gAwIBAgIBADANBgkqhkiG9w0BAQUFADA8MQswCQYDVQQGEwJLUjEc
MBoGA1UECgwTU2Ftc3VuZyBFbGVjdHJvbmljczEPMA0GA1UEAwwGUk9PVENBMCIY
DzE5NjAwMTAxMDAwMDAwWhgPMjA2MDAxMDEwMDAwMDBaMDwxCzAJBgNVBAYTAktS
MRwwGgYDVQQKDBNTYW1zdW5nIEVsZWN0cm9uaWNzMQ8wDQYDVQQDDAZST09UQ0Ew
ggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEKAoIBAQCd67g2hzhbIeSBoFfeqbXi
tzbO4dCWeCigVfmwEDhR1SDA0MfHOVlFpvuFr3WyFPvQZ0ccNrsTpBs5YieI/jZi
FYWO0ktbqQorL1CIFqBL9kAF+34BYtpl98PgJ1grLOH5T3GugJA7Irw0plEFmOfs
IydlUIQHl3oqyMIWPa2nIZ/FGi3hAquEPrvzHZB+QO4c+6tV1WLIaCjn88xkYuwz
uGYxaqJpnGdqhjZRIuHb2DEZPlP1VGdTTAttno36CyWqeHrSC8fXCSu55Zk+1rbC
Py/phOJjSyce2qk0IebETAYLCLqU7ABJxUxrolMrP37OB+Kqe4RWovaeMcdcNOOt
AgMBAAGjUDBOMB0GA1UdDgQWBBTtqd2uYUWvFgzz73eWuf8WrjuxczAfBgNVHSME
GDAWgBTtqd2uYUWvFgzz73eWuf8WrjuxczAMBgNVHRMEBTADAQH/MA0GCSqGSIb3
DQEBBQUAA4IBAQBkwK95x8JCAnY0F2bMwG5+7QfY+ci8s8m1ODi3v19HECS6nG9j
SXgwihEtQ3HqvUler+n7aOeAZlgm+BymM2GvuicveYN/nevIvzlpMOn2L6xU19/H
zM2eoDVfS49+i/cwoi/A7fcZmIYggZho2UJR/GvKc79g6EAhT7/i5alBZF0enMsA
9okzakb/aohQE9SzsEHnhVKpGAjvu0/TJK9WwX6mkiIEJY+mzQMWgEeQt6WWIgAb
gSX9NueH80tpZ9KqFnqnOoLxTAa7k0RPBRwyUO9CDhSnlWIEcsD9sqR2M+niOFnT
KBHcLDDiEU3llprD8FRV3unYrl0F0B2GGdRk
-----END CERTIFICATE-----
"""


def build_message(ssid, password, auth_mode, encrypt_type):
    """Build the APConnectionConfig request the unit expects (no <?xml?> prologue)."""
    inner = "<ConnectionConfig SSID=%s AuthMode=%s" % (quoteattr(ssid), quoteattr(auth_mode))
    if auth_mode == "WEP":
        inner += " Key1=%s" % quoteattr(password)
    elif auth_mode != "OPEN":
        inner += " EncryptType=%s Key1=%s" % (quoteattr(encrypt_type), quoteattr(password))
    inner += "/>"
    return '<Request Type="APConnectionConfig">' + inner + "</Request>"


def make_ssl_context():
    """Legacy mutual-TLS context using the embedded client certificate."""
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    ctx.minimum_version = ssl.TLSVersion.TLSv1
    ctx.set_ciphers("HIGH:!DH:!aNULL:@SECLEVEL=0")
    # load_cert_chain needs a path, so write the embedded PEM to a temp file.
    tmp = tempfile.NamedTemporaryFile("w", suffix=".pem", delete=False)
    try:
        tmp.write(CLIENT_CERT)
        tmp.close()
        ctx.load_cert_chain(tmp.name)
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
    return ctx


def read_device_mac(host, ctx, timeout=6.0):
    """Best-effort: read the module's DUID (its Wi-Fi MAC) before provisioning,
    so a DHCP reservation can be prepared in advance. Returns the MAC
    ("aa:bb:cc:dd:ee:ff") or None if the unit doesn't report it."""
    try:
        sock = ctx.wrap_socket(
            socket.create_connection((host, PORT), timeout=10), server_hostname=host
        )
    except OSError:
        return None
    sock.settimeout(2)
    buf = ""
    asked = False
    deadline = time.time() + timeout
    try:
        while time.time() < deadline:
            try:
                data = sock.recv(4096).decode("utf-8", "replace")
            except socket.timeout:
                data = ""
            if data:
                buf += data
                m = _DUID_RE.search(buf)
                if m:
                    return _format_mac(m.group(1))
            # Once greeted, ask the unit to identify itself (ignored on some units).
            if not asked and ("InvalidateAccount" in buf or "DPLUG" in buf or not data):
                try:
                    sock.sendall(b'<Request Type="DeviceList"></Request>\r\n')
                except OSError:
                    break
                asked = True
            elif not data and asked:
                break
    finally:
        sock.close()
    m = _DUID_RE.search(buf)
    return _format_mac(m.group(1)) if m else None


def provision(ssid, password, auth_mode, encrypt_type, host, ctx, timeout=30):
    """Send the Wi-Fi credentials to a unit in AP mode. Returns True on success."""
    message = build_message(ssid, password, auth_mode, encrypt_type)
    try:
        sock = ctx.wrap_socket(
            socket.create_connection((host, PORT), timeout=10), server_hostname=host
        )
    except OSError as err:
        print("\nCould not reach the air conditioner at %s:%d." % (host, PORT))
        print("Make sure the unit is in AP mode and the computer is connected to")
        print("its SMARTAIRCON network. (%s)" % err)
        return False

    sock.settimeout(3)
    sent = False
    buf = ""
    deadline = time.time() + timeout
    print("Connecting to the air conditioner...")
    while time.time() < deadline:
        try:
            data = sock.recv(4096).decode("utf-8", "replace")
        except socket.timeout:
            continue
        if not data:
            break
        buf += data
        if "InvalidateAccount" in buf and not sent:
            sock.sendall((message + "\r\n").encode())
            sent = True
            print("Sending your Wi-Fi credentials...")
        if "APConnectionConfig" in buf and ("Okay" in buf or "Fail" in buf):
            break
    sock.close()

    if "Okay" in buf:
        print('\nDone! The unit accepted the settings and is joining "%s".' % ssid)
        print("It will now leave the SMARTAIRCON network — reconnect the computer")
        print("to your normal Wi-Fi.")
        return True
    if "Fail" in buf:
        print("\nThe unit rejected the settings. Double-check the network name,")
        print("password and security type, then try again.")
        return False
    print("\nNo response from the unit. Is it in AP mode, and is the computer")
    print("connected to the SMARTAIRCON network?")
    return False


def main():
    parser = argparse.ArgumentParser(
        description="Connect an old Samsung air conditioner to your Wi-Fi (AP-mode provisioning).",
        epilog="With no --ssid/--password, the script asks for them interactively "
        "(the password is hidden as you type).",
    )
    parser.add_argument("--ssid", help="your home Wi-Fi network name (asked if omitted)")
    parser.add_argument(
        "--password", help="your home Wi-Fi password (asked, hidden, if omitted)"
    )
    parser.add_argument(
        "--auth",
        default="WPA2",
        choices=["OPEN", "WEP", "WPA", "WPA2"],
        help="Wi-Fi security type (default: WPA2)",
    )
    parser.add_argument(
        "--encrypt",
        default="AES",
        choices=["TKIP", "AES"],
        help="encryption for WPA/WPA2 (default: AES)",
    )
    parser.add_argument(
        "--host", default=AP_HOST, help="unit address in AP mode (default: %s)" % AP_HOST
    )
    args = parser.parse_args()

    ctx = make_ssl_context()

    # Show the unit's MAC first (if it reports it) so a DHCP reservation can be
    # prepared before the unit joins the network.
    mac = read_device_mac(args.host, ctx)
    if mac:
        print("Air conditioner found — its Wi-Fi MAC address is: %s" % mac.upper())
        print(
            "Tip: if you'd like it to keep a fixed IP, you can add a DHCP reservation\n"
            "for this MAC on your router now, before it joins your network.\n"
        )

    ssid = args.ssid if args.ssid is not None else input("Wi-Fi network name (SSID): ").strip()
    if not ssid:
        print("No network name given; aborting.")
        sys.exit(2)
    if args.auth == "OPEN":
        password = ""
    elif args.password is not None:
        password = args.password
    else:
        password = getpass.getpass("Wi-Fi password: ")

    ok = provision(ssid, password, args.auth, args.encrypt, args.host, ctx)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
