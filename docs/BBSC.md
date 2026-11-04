# BBSC: Bloodborne seamless co-op in the port

BBSC (seamless co-op for Bloodborne, GPL-2.0-or-later; https://seamlesshunt.com) keeps a co-op
session alive through deaths, lamps, area changes, bosses and the Hunter's Dream, for up to five
hunters. It is written for shadp2p (a shadPS4 fork); the port carries it in its online module.

## Switching it on

Launcher, Online page: "Play online" and "Seamless co-op (BBSC)". Every player needs it on and the
same server: a shadNet server with BBSC's game server next to it. Without the switch nothing of
BBSC is installed and the online module behaves as before.

The launcher's defaults are BBSC's public servers, Seamless Hunt (0.6): shadNet
`play.seamlesshunt.com:31313`, WebAPI `http://play.seamlesshunt.com:31315`, game server
`http://play.seamlesshunt.com` (plain http: BBSC's game server listens on 20443 without TLS). The
account (online id and password) is made on https://seamlesshunt.com; the launcher only takes it.
shadPS4's public shadNet server (`srv.shadps4.net`) accepts only shadPS4's own builds since
2026-10-12: it signs the port out (notification 19) and then refuses its logins for a while.

BBSC's game server on this PC: when the server's own game server does not answer (its
`:20443/bb-eu/ss.info` timed out for players while the rest of the public server worked,
2026-10-14), `run.sh` starts BBSC's `bbsc_gameserver.py` (`scripts/bbsc_gameserver`, from
BBSC-Server-Linux) on 127.0.0.1:20443 and points the game's server there; it sends the summon
calls to the shadNet server's WebAPI, accounts and bells go to the shadNet server as before.
Messages and bloodstains are then this PC's only. It stops with the game; its logs and data are in
`<user>/bbsc/`. `BB_BBSC_LOCAL_SERVER=1` always, `=0` never, `auto` (default) when the server's
does not answer within 5 s. (BBSC's own `BBSC_RELAY` is for the TCP relay in its Windows DLL; the
port's relay is the UDP one on port 3478 of the shadNet server.)

bbglorp also uses that fallback if the public status response is invalid or lacks the game's
regional sections. A successful shadNet login is separate from the game's server-status step:
an EU-only `gameurl2` response can produce "Failed to resolve Bloodborne server status" on
other game regions, leaving the Kin Bell disabled as offline. The bundled server supplies the
same status, URLs and timers for US (1), EU (2), JP (3) and Asia (4), with every language entry.
The launcher waits for its status response before starting the game. Summons still use the
shared shadNet WebAPI; messages and bloodstains are local while the fallback is active.

Environment: `BB_ONLINE=1 BB_BBSC=1` (what the launcher sets). BBSC's own switches
(`SHADPS4_BBSC_*`, `SHADPS4_BLOODBORNE_*`, see `gpu/bbnet20/bbsc/core/bbsc_persistence.h`) work as
in BBSC: most features are on by default, `=0` turns one off.

## Where it lived in the shadp2p module (history)

The shadp2p module (`gpu/bbnet`, `libbbnet.so`) was removed on 2026-10-26; BBSC lives in
`gpu/bbnet20` now (the table under "On the shadPS4 0.20 stack" below). The first port's layout:

| Part | Files |
|---|---|
| Game code (hooks, byte patches, session policy, world sync) | `gpu/bbnet/shadps4/core/bloodborne_re.cpp`, `bbsc_*.{h,cpp}`, `bbsc_messages.inc` (BBSC's, unchanged) |
| Network (signaling packets, relay fallback, room replay, placement header) | BBSC's changes merged into `gpu/bbnet/shadps4/core/libraries/network` and `np/` (three-way merge against shadp2p 6e97b40, the base of both); the relay as in BBSC's BBport build of 2026-10-14 (below) |
| NP lookup (`sceNpLookupNpId`, a third and later player) | `gpu/bbnet/shadps4/core/libraries/np/np_utility.{h,cpp}` (BBSC's), registered in `bbnet_register` |
| Hooks in the game's code (any game) | `gpu/shim/bbport_guest_code_hooks.{h,cpp}`: shadPS4's `Core::InstallGuestCodeHook` interface, the port's trampolines |
| What BBSC asks of shadPS4 | `gpu/bbnet/include/` (`core/cpu_patches.h`, `core/memory.h`, `core/file_format/psf.h`, `common/memory_patcher.h`), `gpu/bbnet/bbsc_glue.cpp` |
| Local game server | `scripts/bbsc_gameserver/` (BBSC's, unchanged; NoDreamForHunter format, MIT), chosen by `scripts/online.py bbsc-local`, started by `run.sh` |
| Start | `bbnet_image_ready` (`gpu/bbnet/bbnet_glue.cpp`), called by the runtime once the image is mapped and patched (`src/probe.c` -> `runtime_net_image_ready`) |

Differences from BBSC's own builds:
- The game's code stays writable while BBSC is on (`Core::KeepGuestCodeWritable`): BBSC writes
  byte patches into it and switches some while the game runs; the port's own code patches leave it
  so too.
- Any retail Bloodborne 1.09 (every region runs the same executable) counts as CUSA03173; every
  BBSC site is still byte-checked.
- Saves: `BBSC_SAVE_DIR` points at `<user>/savedata/<id>/CUSA00207/SPRJ0005` (the port's layout).
- Its loading screen is a line in the port's overlay (`bbgpu_overlay_banner`); the cinematic
  camera (F1, keyboard and mouse) gets the window's events through `bbgpu_add_event_filter`.
- Not ported: the animated title card (off by default in BBSC too), Discord status, its launcher's
  account creation and server cards (the port's launcher takes the server address and account).
- The "bell check" trace hook does not install (BBSC's own byte patch is at the same address); it
  only logs.

## Updates taken

- 2026-10-14, BBSC 0.0.1 "bug fixes" (its BBport build, `bbport-1.7.2-bbsc.patch`): the relay goes
  through the server for every known peer from the first frame (`SHADPS4_P2P_RELAY=auto` or
  `direct` = the old "direct first, relay after 2 s", `=0` off), peers are kept by online id with
  every endpoint as an alias (the one-way relay behind CGNAT that died after 30 s); the NP lookup
  above. Its signaling and matching files were already the same as here. The fixes inside
  `bbsc.dll` of that release (death and respawn, sign targeting, relay TCP framing) have no
  published source yet; they come in when BBSC publishes it.

- 2026-11-03, two unmerged BBSC pull requests, on top of 0.0.2. Neither has had a two-player test
  in this port. PR #9 covers guest failures in boss wipes, and may address BBSC issue #44 (guest stuck
  spectating); it adds relay/signaling packet "SHAD" 0x2B for the host's bloodstain, so both players
  need this build. The PR only added the mod relay's receive, so `bbsc_relay_client.cpp` and
  `signaling_handler.cpp` carry the port's own branches. PR #39 keeps a joining guest's screen black
  until the guest is placed beside the host.

## Checks

`out/dev/verify/verify.sh NAME BB_ONLINE=1 BB_BBSC=1`: loads the save offline-capable, 14 self-tests
pass, no faults (2026-10-14). Real co-op needs two players on a BBSC server.

## On the shadPS4 0.20 stack (2026-10-16)

BBSC now runs in `gpu/bbnet20` (`libbbnet20.so`: shadPS4 v0.20.0's network, NP and shadNet code,
see `gpu/bbnet20/SHADNET-PORT.md`); the shadp2p module (`libbbnet.so`) was kept as a fallback
until 2026-10-26, then removed. Seamless Hunt is the launcher's first pool, The Hunter's Dream the second (no
BBSC there). Ported, against the 0.20 sources:

| BBSC part | Where in `gpu/bbnet20` |
|---|---|
| Game code, unchanged | `bbsc/core/` (`bloodborne_re.cpp`, `bbsc_*`), UI stand-ins `bbsc/bbsc_glue.cpp`, start in `bbnet_glue.cpp` (`bbnet_image_ready`) |
| Signaling packets 0x20 (follow) and 0x22 (world flags); 2 KB receive buffer | `vendor/.../np_signaling/np_signaling_state.h`, `np_signaling_bbsc.h`, `np_signaling_helpers.cpp` (senders), `np/signaling_handler.cpp` (receive) |
| Room replay after a stage load, leave-room trace | `np_matching2_mm.cpp` (`BbscReplayRoomMembers`), `np_matching2.cpp` |
| Summon route, host-placement header, connect-first area, stale-record cleanup, fast sign | `network/http.cpp` (block before `sceHttpSendRequest`) |
| UDP relay (BBR1, port 3478 of the shadNet server) | `core/net/p2p_relay.{h,cpp}`, hooked in `p2p_transport.cpp` (`SendPacket`, receive loop, keep-alive); fed by `np_matching2_mm.cpp`, `signaling_handler.cpp` |
| `sceNpLookupNpId` | 0.20's own (`np_utility`), shadNet lookup |

Not ported: the static peer map (`SHADPS4_BBSC_PEERS`, a test aid), the bell "rejoin fix" of the
shadp2p signaling (0.20 answers an Offer on an established transport with an Accept, so the stuck
case of shadp2p may not exist; needs a real two-player test), the summon capture files.
Untested with a second player: everything above except that the module loads and BBSC installs
its hooks (`BB_ONLINE=1 BB_BBSC=1`, 2026-10-16).

Seamless Hunt's own releases (BBSC 0.0.1) fixed items not showing, death and respawn, sign
targeting and the relay framing inside `bbsc.dll` (a Windows mod for shadPS4/BBport); that source
is not published, so those fixes are not here.

## bbglorp private hosting

Online → Join private server, above the Host section, is for the player connecting to a friend:
their address, Test connection, Use this server, and the registration key, email and Create account.
The test (`scripts/private_server.py check`) performs a shadNet handshake, a real UDP STUN ping,
WebAPI `/status`, the game's `ss.info` check and a relay TCP connect, in parallel with one deadline.
A pass shows only that those services answer from this PC. It does not show that two-player gameplay
works. Run from the host's own address it also skips the firewall, and the result says so; only a run
from the friend's PC tests their route.

Security limits of private hosting: shadNet logins and registration use unencrypted TCP, and the
host's server receives the password, so use one that is used nowhere else. The relay on TCP 20444
has no authentication and its sender ids are written by clients, so anyone who can reach that port
can read and forge session frames. Changing that would break compatibility with BBSC's protocol.
Keep these ports on a LAN or VPN; Start warns when the address is public. The game server caps
request bodies at 1 MiB and the relay at 16 connections.

Online → Host private server manages shadNet (TCP 31313, UDP 31314 and WebAPI TCP 31315),
the game server (TCP 20443) and BBSC's TCP 20444 relay. The server source is pinned to the
checksum-verified official BBSC 0.0.2 Linux server archive; both platforms compile it natively.
No root installer or system service is run. The selected IPv4 address must belong to this PC's
LAN or virtual LAN. The launcher does not change the firewall or install a VPN.

Only one player starts the private server. Keep their launcher open; starting/stopping the game
keeps the private server running. Stop server or closing the launcher stops its owned services.
Accounts, the registration key and logs live in `<save folder>/private-server/`, outside the
AppImage/package. An existing local helper on the same address/ports must be stopped first.

The host presses Use address and a friend presses Use this server. Both set all three server fields,
enable BBSC and online, disable the offline-choice patch and turn off UPnP for LAN/VPN.
Create an account in the Join section using the Online ID/password fields and an email. Public-server
accounts are separate. On startup the host's address and registration key are filled into the Join
section. Copy details includes the key while hosting, so share those details privately. A joining
friend enters that key to register their own account.
Use the same in-game Network password, host Hunt Bell and guest Kin Bell. The live log's READY
means local service checks passed; it does not establish that a friend's firewall/VPN connection
or two-player gameplay succeeds. Use matching bbglorp builds on both PCs.

The HTTP fallback's loopback address is separate from the shared BBSC relay (`BBSC_RELAY`).
The launcher pins that relay before changing the HTTP server address and logs its endpoint.
The guest-hook installer also tracks exact byte ranges, allowing adjacent summon callbacks.
Packaging tests cover registration/key rejection, password matching, two-way TCP relay traffic,
restart persistence and owned-process cleanup. Real gameplay remains a separate two-player test.

The UDP transport also keeps using a direct peer that answered when no peer relay traffic has
arrived. Previously the default forced-relay policy immediately undid OnReceive's switch back
to direct and suppressed subsequent direct packets. A production-source regression reproduces
that failure, checks repeated direct sends, and verifies that real relayed peer traffic still
switches to the working relay. First direct replies are recorded in the BBSC timeline.

### Room signaling diagnostics

A successful Sig1 connection is not sufficient for a room join: Matching2 must also report
`Matching2 signaling established`. Room replies and member notifications arrive on the shadNet
reader thread. Endpoint lookup must run on the activation worker so the reader can receive the
lookup reply; an unresolved reader-thread lookup must not discard the room peer.

The log now records room lookup queuing, peer linkage, and the existing established callback.
Short BBSC progress snapshots (including an empty six-byte `SHAD 26 00` message) are processed
as BBSC messages, never as a raw six-byte STUN reply. Only the configured matching server's
UDP endpoint may supply STUN replies. The packet classification regression covers this collision
and rejects endpoint updates from other peers/ports.

These corrections require a two-player gameplay retry before claiming the joining failure is
resolved. Server lifecycle, relay transport and launcher startup checks cannot establish that.

The official shadNet server source in BBSC 0.0.2 still expects STUN requests/replies with the
older four-byte `FFFF FFFF` virtual-port header. The client uses that envelope only for the
21-byte STUN ping to its configured server, and accepts an exact six-byte legacy echo only
from that server. Peer signaling/gameplay keeps the modern codec and its communication-id,
encryption and signature validation.

`tests/test_matching2_native.sh` drives two real native networking modules through initial Sig1
activation, Matching2 room creation/join and bidirectional datagrams on virtual port 30. It uses
the official local server, temporary accounts and unrelated renderer-host ABI stubs, without game
files. Its relay case disables STUN and forwards opaque relay packets; its direct case uses the
server's real STUN listener with no relay fixture, and rejects pseudo-endpoint fallback. This is
run before AppImage packaging. Character loading and real Internet gameplay still need testing.
